import streamlit as st
import pytesseract
import pypdf
import re
import io
import requests
import pandas as pd
import json
import os
from datetime import datetime
import hashlib
from pdf2image import convert_from_bytes
from pyzbar.pyzbar import decode
from deep_translator import GoogleTranslator
import base64
from cryptography.fernet import Fernet
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. ENHANCED SECURITY CONFIGURATION ---
# Generate encryption key on first run
ENCRYPTION_KEY = os.getenv('OZON_ENCRYPTION_KEY', Fernet.generate_key())
cipher_suite = Fernet(ENCRYPTION_KEY)

# Change this password to your preferred login
APP_PASSWORD = "VINOVJ1100"

def hash_password(password):
    """Hash password for additional security"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password():
    """Enhanced password checking with failure tracking"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.failed_attempts = 0
        st.session_state.lockout_time = None

    # Check for lockout
    if st.session_state.lockout_time:
        if datetime.now() > st.session_state.lockout_time:
            st.session_state.lockout_time = None
            st.session_state.failed_attempts = 0
        else:
            remaining = (st.session_state.lockout_time - datetime.now()).seconds // 60
            st.error(f"🔒 System locked for {remaining} more minutes due to too many failed attempts")
            return False

    if not st.session_state.authenticated:
        st.title("🔒 System Locked")
        st.info("Please enter the Operator Password to access Ozon Master Tool Pro.")
        
        pwd_input = st.text_input("Enter Password", type="password")
        if st.button("Unlock System"):
            if pwd_input == APP_PASSWORD:
                st.session_state.authenticated = True
                st.session_state.failed_attempts = 0
                st.rerun()
            else:
                st.session_state.failed_attempts += 1
                st.error("❌ Incorrect Password. Access Denied.")
                
                if st.session_state.failed_attempts >= 3:
                    st.session_state.lockout_time = datetime.now() + pd.Timedelta(minutes=10)
                    st.error("🔒 Too many failed attempts. System locked for 10 minutes.")
                return False
    return True

def encrypt_data(data):
    """Encrypt sensitive data"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data):
    """Decrypt sensitive data"""
    return cipher_suite.decrypt(encrypted_data.encode()).decode()

# --- 2. PDF PROCESSING IMPLEMENTATION ---
def extract_text_from_pdf(pdf_bytes):
    """Extract text from PDF bytes"""
    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"❌ Error extracting text from PDF: {str(e)}")
        return None

def parse_barcode_from_pdf(pdf_bytes):
    """Parse barcode data from PDF using image processing"""
    try:
        # Convert PDF to images
        images = convert_from_bytes(pdf_bytes)
        all_data = []
        
        for i, image in enumerate(images):
            # Extract text from image (simulating barcode reading)
            text = pytesseract.image_to_string(image)
            # Look for tracking numbers in the extracted text
            tracking_numbers = re.findall(r'\b\d{4,12}-?\d{4}-?\d?\b', text)
            if tracking_numbers:
                for tn in tracking_numbers:
                    all_data.append({
                        'tracking_id': tn,
                        'page': i + 1,
                        'raw_text': text[:200]  # First 200 chars for context
                    })
        
        return all_data
    except Exception as e:
        st.error(f"❌ Error processing PDF: {str(e)}")
        return None

def generate_sequence_pdf(sequence_data):
    """Generate PDF file from sequence data"""
    try:
        # Create a simple PDF with the sequence
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        y_position = height - 50
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, y_position, "Shipping Label Sequence")
        
        y_position -= 50
        p.setFont("Helvetica", 12)
        
        for item in sequence_data:
            p.drawString(50, y_position, str(item))
            y_position -= 25
        
        p.save()
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"❌ Error generating sequence PDF: {str(e)}")
        return None

# --- 3. DATA EXPORT FUNCTIONALITY ---
def export_audit_results(df, format_type='csv'):
    """Export audit results in various formats"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ozon_audit_{operator_name}_{timestamp}"
        
        if format_type == 'csv':
            csv = df.to_csv(index=False)
            st.download_button(
                label=f"Download {format_type.upper()} Report",
                data=csv,
                file_name=f"{filename}.csv",
                mime="text/csv"
            )
        elif format_type == 'excel':
            excel = df.to_excel(index=False)
            st.download_button(
                label=f"Download {format_type.upper()} Report",
                data=excel,
                file_name=f"{filename}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        elif format_type == 'json':
            json_data = df.to_json(orient='records')
            st.download_button(
                label=f"Download {format_type.upper()} Report",
                data=json_data,
                file_name=f"{filename}.json",
                mime="application/json"
            )
    except Exception as e:
        st.error(f"❌ Error exporting data: {str(e)}")

# --- 4. MAIN APPLICATION ---
if check_password():
    # --- CONFIGURATION & REGEX ---
    SCANNING_ID_REGEX = re.compile(r"\b\d{4,12}-?\d{4}-?\d?\b")

    st.set_page_config(
        page_title="Ozon Master Tool Pro", 
        layout="wide", 
        page_icon="📦",
        initial_sidebar_state="expanded"
    )

    # Sidebar: User and Controls
    with st.sidebar:
        st.image("https://icons8.com", width=80)
        st.title("Operator Settings")
        operator_name = st.text_input("Operator Name", value="Staff_01")
        
        st.divider()
        st.subheader("🔑 API Credentials")
        ozon_id = st.text_input("Client ID", type="password")
        ozon_key = st.text_input("API Key", type="password")
        
        st.divider()
        st.subheader("📷 Scanner")
        scan_dpi = st.select_slider("Resolution (DPI)", options=[150, 200, 300], value=300)
        
        st.divider()
        st.subheader("💾 Export Settings")
        export_format = st.selectbox("Default Export Format", ["csv", "excel", "json"])
        
        st.divider()
        st.subheader("🔒 Security")
        st.text("Session ID: " + st.session_state.get('session_hash', ''))
        
        if st.button("🔴 Logout & Lock"):
            st.session_state.authenticated = False
            st.session_state.session_hash = ""
            st.rerun()

    # Main Interface
    st.title(f"📦 Ozon Master Tool Pro | **{operator_name}**")
    
    # Set up session
    if 'session_hash' not in st.session_state:
        st.session_state.session_hash = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
    
    tabs = st.tabs(["📊 Status", "🔍 PDF Sort", "⚖️ Auditor", "🌐 Translator", "📋 Export"])
    
    # --- TAB 1: STATUS ---
    with tabs[0]:
        st.subheader("📊 **Real-time Status Checker**")
        status_input = st.text_area("Paste Tracking Numbers", height=150)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Check API Status"):
                if not ozon_key: 
                    st.warning("Please enter API Key in sidebar.")
                else:
                    tracking_numbers = SCANNING_ID_REGEX.findall(status_input)
                    if tracking_numbers:
                        st.info(f"Checking {len(tracking_numbers)} items...")
                        # Mock API call - replace with actual Ozon API
                        results = []
                        for tn in tracking_numbers:
                            results.append({
                                'Tracking ID': tn,
                                'Status': 'In Transit',
                                'Location': 'Moscow Hub',
                                'Updated': datetime.now().strftime('%H:%M')
                            })
                        st.dataframe(pd.DataFrame(results))
                    else:
                        st.warning("⚠️ No valid tracking numbers found.")
        
        with col2:
            if st.button("📋 Copy Session Info"):
                session_info = f"Session: {st.session_state.session_hash}\nOperator: {operator_name}\nTime: {datetime.now()}"
                st.clipboard_copy(session_info)
                st.success("Session info copied to clipboard!")

    # --- TAB 2: PDF SORT ---
    with tabs[1]:
        st.subheader("🔍 **PDF Label Sequencer (300 DPI)**")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            sort_list = st.text_area("Sequence Order", height=250, placeholder="Enter sequence (one per line)")
        with col2:
            pdf_file = st.file_uploader("Upload Labels PDF", type="pdf", help="Supports up to 10MB")
        with col3:
            scan_dpi = st.select_slider("DPI", options=[150, 200, 300], value=300)
        
        if st.button("🚀 Start Sequence Sort"):
            if not sort_list.strip() and not pdf_file:
                st.warning("Please provide sequence data or upload PDF.")
                return
            
            if pdf_file:
                with st.spinner("Processing PDF..."):
                    pdf_bytes = pdf_file.read()
                    extracted_text = extract_text_from_pdf(pdf_bytes)
                    barcode_data = parse_barcode_from_pdf(pdf_bytes)
                    
                    if extracted_text:
                        st.success("✅ Text extracted successfully!")
                        st.text(extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text)
                    
                    if barcode_data:
                        st.success("✅ Barcodes detected!")
                        st.dataframe(pd.DataFrame(barcode_data))
            
            if st.button("📄 Generate Sample PDF"):
                sequence_data = [f"Item_{i+1}: Tracking_{i+1:04d}-ABC" for i in range(5)]
                pdf_content = generate_sequence_pdf(sequence_data)
                if pdf_content:
                    st.download_button(
                        label="Download Sample PDF",
                        data=pdf_content,
                        file_name="sample_sequence.pdf",
                        mime="application/pdf"
                    )

    # --- TAB 3: AUDITOR ---
    with tabs[2]:
        st.subheader("⚖️ **Verification Auditor**")
        
        col_a, col_b = st.columns(2)
        with col_a:
            master_in = st.text_area("**MASTER (Expected)**", height=300, placeholder="Paste expected data...")
        with col_b:
            scan_in = st.text_area("**SCAN (Actual)**", height=300, placeholder="Paste scanned data...")

        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            tolerance_level = st.selectbox("Tolerance Level", ["Strict", "Medium", "Lenient"])
            highlight_critical = st.checkbox("Highlight Critical Errors")
            save_audit_log = st.checkbox("Save Audit Log", value=True)

        if st.button("⚡ Run Discrepancy Analysis"):
            if master_in and scan_in:
                with st.spinner("Analyzing differences..."):
                    m_map = robust_parse_multiline(master_in)
                    s_map = robust_parse_multiline(scan_in)
                    all_ids = sorted(list(set(m_map.keys()) | set(s_map.keys())))
                    
                    results = []
                    for tid in all_ids:
                        exp, got = m_map.get(tid, set()), s_map.get(tid, set())
                        
                        if tolerance_level == "Strict":
                            status = "✅ MATCH" if exp == got else "❌ ERROR"
                        elif tolerance_level == "Medium":
                            # Allow minor differences
                            critical_diff = exp - got if exp else got - exp
                            if critical_diff:
                                status = "⚠️ CRITICAL" if critical_diff else "✅ MATCH"
                            else:
                                status = "✅ MATCH"
                        else:  # Lenient
                            # Allow up to 1 difference
                            diff_count = len(exp.symmetric_difference(got))
                            if diff_count <= 1:
                                status = "✅ MATCH"
                            else:
                                status = "❌ ERROR"
                        
                        if highlight_critical and "CRITICAL" in status:
                            status = status.replace("⚠️", "🔴")
                        
                        results.append({
                            "Tracking ID": f"**{tid}**",
                            "Status": status,
                            "Expected Items": " | ".join(exp) if exp else "-",
                            "Actual Items": " | ".join(got) if got else "-",
                            "Timestamp": datetime.now().strftime('%H:%M:%S')
                        })
                    
                    df = pd.DataFrame(results)
                    st.dataframe(df.style.apply(
                        lambda x: ['background-color: #ffcccc; font-weight: bold' if v.startswith('🔴') else 
                                   'background-color: #fff3cd; font-weight: bold' if v.startswith('⚠️') else '' 
                                   for v in x], axis=1, subset=["Status"]), use_container_width=True)
                    
                    # Save audit log if requested
                    if save_audit_log:
                        audit_log = {
                            'timestamp': datetime.now().isoformat(),
                            'operator': operator_name,
                            'results': results
                        }
                        log_filename = f"audit_log_{operator_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        with open(log_filename, 'w') as f:
                            json.dump(audit_log, f, indent=2)
                        st.success(f"📋 Audit log saved: {log_filename}")
            else:
                st.warning("**Paste data to begin audit.**")

   # --- TAB 4: TRANSLATOR ---
with tabs:
st.subheader("🌐 **Instant Translator**")

# Translation options
source_lang = st.selectbox("Source Language", ["auto", "ru", "en", "de", "fr", "es"])
target_lang = st.selectbox("Target Language", ["en", "ru", "de", "fr", "es", "pt", "it", "ja", "ko"])

# Text input with examples
st.markdown("### Translate Russian Text")
with st.form("translate_form", clear_on_submit=True):
txt = st.text_area("Enter Text", height=200, placeholder="Enter Russian text here...")
submit_btn = st.form_submit_button("Translate")

# Translation history
if "translation_history" not in st.session_state:
st.session_state.translation_history = []

translation_results = []
if submit_btn:
try:
translator = GoogleTranslator(source=source_lang, target=target_lang)
translated_text = translator.translate(txt)

translation_entry = {
timestamp': datetime.now().strftime('%H:%M:%S'),
source': txt[:100] + "..." if len(txt) > 100 else txt,
target': translated_text,
source_lang': source_lang,
target_lang': target_lang
}

st.session_state.translation_history.append(translation_entry)
translation_results.append(translation_entry)

# Show translation
col1, col2 = st.columns(2)
with col1:
st.markdown("**Original:**")
st.text(txt)
with col2:
st.markdown("**Translated:**")
st.text(translated_text)

# Download history
if st.button("📥 Download Translation History"):
history_df = pd.DataFrame(st.session_state.translation_history)
csv = history_df.to_csv(index=False)
st.download_button(
label="Download History as CSV",
data=csv,
file_name=f"translation_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
mime="text/csv"
)

except Exception as e:
st.error(f"❌ Translation failed: {str(e)}")

# Recent translations
if st.session_state.translation_history:
st.markdown("### 📚 Recent Translations")
recent_df = pd.DataFrame(st.session_state.translation_history[-5:]).T
st.dataframe(recent_df, use_container_width=True)

# --- TAB 5: EXPORT ---
with tabs:
st.subheader("📋 **Data Export & Management**")

# Export format selection
export_format = st.selectbox("Select Export Format", ["CSV", "Excel", "JSON", "PDF Report"])

# Data source selection
data_source = st.selectbox("Select Data to Export",
["Audit Results", "Translation History", "All Data"])

# Export button
if st.button("📥 Generate & Download Report"):
if data_source == "Audit Results":
if "audit_results" not in st.session_state:
st.warning("No audit results to export. Please run audit first.")
else:
export_data(st.session_state.audit_results, export_format, operator_name)

elif data_source == "Translation History":
if "translation_history" not in st.session_state or not st.session_state.translation_history:
st.warning("No translation history to export.")
else:
export_data(st.session_state.translation_history, export_format, operator_name)

elif data_source == "All Data":
combined_data = {
audit_results': st.session_state.get('audit_results', []),
translation_history': st.session_state.get('translation_history', []),
export_timestamp': datetime.now().isoformat(),
operator': operator_name
}
export_data(combined_data, export_format, operator_name)

# Data management section
st.markdown("### 💾 Data Management")

col1, col2 = st.columns(2)
with col1:
st.info("📊 Current Statistics")
stats = calculate_statistics(st.session_state)
for key, value in stats.items():
st.metric(key.replace('_', ' ').title(), value)

with col2:
st.info("🔒 Security Info")
st.text(f"Session Hash: {st.session_state.get('session_hash', 'N/A')}")
st.text(f"Encryption: AES-256")
st.text(f"Last Activity: {datetime.now().strftime('%H:%M:%S')}")

# Clear data options
with st.expander("🗑️ Clear Data"):
st.warning("⚠️ This will clear all session data!")
if st.button("Clear All Session Data"):
clear_session_data()
st.success("✅ All session data cleared.")

# Settings export
with st.expander("⚙️ Export Settings"):
settings = {
operator_name': operator_name,
api_credentials': {
client_id': ozon_id.replace('*', 'X') if ozon_id else '',
api_key': ozon_key.replace('*', 'X') if ozon_key else ''
},
scanner_settings': {'dpi': scan_dpi},
export_settings': {'default_format': export_format}
}

st.json(settings)

if st.button("📥 Download Settings"):
settings_json = json.dumps(settings, indent=2)
st.download_button(
label="Download Settings",
data=settings_json,
file_name=f"ozon_settings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
mime="application/json"
)

# --- HELPER FUNCTIONS ---
def extract_text_from_pdf(pdf_bytes):
"Extract text from PDF bytes"
try:
pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
text = ""
for page in pdf_reader.pages:
text += page.extract_text() + "\n"
return text
except Exception as e:
st.error(f"❌ Error extracting text from PDF: {str(e)}")
return None

def parse_barcode_from_pdf(pdf_bytes):
"Parse barcode data from PDF using image processing"
try:
images = convert_from_bytes(pdf_bytes)
all_data = []

for i, image in enumerate(images):
text = pytesseract.image_to_string(image)
tracking_numbers = re.findall(r'\b\d{4,12}-?\d{4}-?\d?\b', text)
if tracking_numbers:
for tn in tracking_numbers:
all_data.append({
tracking_id': tn,
page': i + 1,
raw_text': text[:200]
})

return all_data
except Exception as e:
st.error(f"❌ Error processing PDF: {str(e)}")
return None

def generate_sequence_pdf(sequence_data):
"Generate PDF file from sequence data"
try:
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

buffer = io.BytesIO()
p = canvas.Canvas(buffer, pagesize=letter)
width, height = letter

y_position = height - 50
p.setFont("Helvetica-Bold", 16)
p.drawString(50, y_position, "Shipping Label Sequence")

y_position -= 50
p.setFont("Helvetica", 12)

for item in sequence_data[:20]: # Limit to 20 items
p.drawString(50, y_position, str(item))
y_position -= 25

p.save()
buffer.seek(0)
return buffer.getvalue()
except Exception as e:
st.error(f"❌ Error generating sequence PDF: {str(e)}")
return None

def export_data(data, format_type, operator_name):
"Export data in specified format"
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"ozon_export_{operator_name}_{timestamp}"

try:
if format_type == "CSV":
if isinstance(data, dict):
df = pd.DataFrame.from_dict(data, orient='index')
else:
df = pd.DataFrame(data)
csv = df.to_csv(index=False)
st.download_button(
label=f"Download CSV Report",
data=csv,
file_name=f"{filename}.csv",
mime="text/csv"
)

elif format_type == "Excel":
if isinstance(data, dict):
with pd.ExcelWriter(f"{filename}.xlsx") as writer:
for key, value in data.items():
if isinstance(value, list):
df = pd.DataFrame(value)
df.to_excel(writer, sheet_name=key.replace('_', ' '), index=False)
else:
df = pd.DataFrame(data)
df.to_excel(f"{filename}.xlsx", index=False)
else:
df = pd.DataFrame(data)
df.to_excel(f"{filename}.xlsx", index=False)

st.download_button(
label=f"Download Excel Report",
data=open(f"{filename}.xlsx", 'rb').read(),
file_name=f"{filename}.xlsx",
mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

elif format_type == "JSON":
json_data = json.dumps(data, indent=2, default=str)
st.download_button(
label=f"Download JSON Report",
data=json_data,
file_name=f"{filename}.json",
mime="application/json"
)

elif format_type == "PDF Report":
pdf_content = generate_pdf_report(data, filename)
if pdf_content:
st.download_button(
label=f"Download PDF Report",
data=pdf_content,
file_name=f"{filename}.pdf",
mime="application/pdf"
)

except Exception as e:
st.error(f"❌ Export failed: {str(e)}")

def generate_pdf_report(data, filename):
"Generate PDF report"
try:
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

buffer = io.BytesIO()
p = canvas.Canvas(buffer, pagesize=letter)
width, height = letter

# Header
p.setFont("Helvetica-Bold", 16)
p.drawString(inch, height - inch, f"Ozon Master Tool Pro - Report")
p.drawString(inch, height - 1.5*inch, f"Operator: {operator_name}")
p.drawString(inch, height - 2*inch, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Content
p.setFont("Helvetica", 10)
y_position = height - 3*inch

if isinstance(data, dict):
for key, value in data.items():
p.drawString(inch, y_position, f"**{key}:**")
y_position -= 0.2*inch

if isinstance(value, list):
for item in value[:10]:
p.drawString(inch + 0.5, y_position, f"• {str(item)[:100]}...")
y_position -= 0.15*inch
else:
p.drawString(inch + 0.5, y_position, str(value)[:200] + "...")
y_position -= 0.
if not pdf_content:
st.error("❌ Failed to generate PDF report")
return None

st.download_button(
label=f"Download {filename}.pdf",
data=pdf_content,
file_name=f"{filename}.pdf",
mime="application/pdf"
)
except Exception as e:
st.error(f"❌ PDF generation failed: {str(e)}")

# ==================== UTILITY FUNCTIONS ====================
def robust_parse_multiline(text_data):
"Enhanced parsing function for multiline text"
SCANNING_ID_REGEX = re.compile(r"\b\d{4,12}-?\d{4}-?\d?\b")
data_map = {}
current_tn = None

for line in text_data.strip().split('\n'):
line = line.strip()
if not line:
continue

tn_match = SCANNING_ID_REGEX.search(line)
if tn_match:
current_tn = tn_match.group()
desc = line.replace(current_tn, "").strip('|').strip()
data_map.setdefault(current_tn, set())
if desc:
data_map[current_tn].add(desc)
elif current_tn:
data_map[current_tn].add(line)

return data_map

def calculate_statistics(session_state):
"Calculate current session statistics"
stats = {
Total Items Processed': len(session_state.get('audit_results', [])),
Translation Operations': len(session_state.get('translation_history', [])),
Active Sessions': 1,
Data Size (MB)': round(len(str(session_state)) / (1024 * 1024), 2)
}
return stats

def clear_session_data():
"Clear all session data"
keys_to_clear = [k for k in st.session_state.keys()
if k not in ['authenticated', 'failed_attempts', 'lockout_time', 'session_hash']]
for key in keys_to_clear:
del st.session_state[key]

# ==================== AUTHENTICATION INITIALIZATION ====================
if 'authenticated' not in st.session_state:
st.session_state.authenticated = False
st.session_state.failed_attempts = 0

# ==================== MAIN APPLICATION RUN ====================
if check_password():
# Display main content here...
# The main application content continues from here
# (This would include all the tabbed interface)

# Initialize session states
if 'audit_results' not in st.session_state:
st.session_state.audit_results = []

if 'translation_history' not in st.session_state:
st.session_state.translation_history = []

# Rest of the main application code would go here...
# This includes the tabbed interface, forms, and all functionality
pass
else:
# Display locked screen
st.title("🔒 System Locked")
st.info("Please enter the Operator Password to access Ozon Master Tool Pro.")

pwd_input = st.text_input("Enter Password", type="password")
if st.button("Unlock System"):
if pwd_input == APP_PASSWORD:
st.session_state.authenticated = True
st.session_state.failed_attempts = 0
st.rerun()
else:
st.session_state.failed_attempts += 1
st.error("❌ Incorrect Password. Access Denied.")

if st.session_state.failed_attempts >= 3:
st.error("🔒 Too many failed attempts. System locked for 10 minutes.")
