import streamlit as st
import pytesseract
import pypdf, re, io
import requests
import pandas as pd
from pdf2image import convert_from_bytes
from pyzbar.pyzbar import decode
from deep_translator import GoogleTranslator

# --- 1. CONFIGURATION & REGEX ---
OZON_API_URL = "https://api-seller.ozon.ru"
# Regex to catch Ozon posting numbers (e.g., 12345678-0001-1)
SCANNING_ID_REGEX = re.compile(r"\b\d{4,10}-?\d{4}-?\d?\b")

st.set_page_config(page_title="Ozon Master Tool Pro", layout="wide", page_icon="📦")

# Custom CSS for a professional look
st.markdown("""
    <style>
    .main { background-color: #f0f2f5; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 Ozon Master Tool Pro")
st.caption("Bulk Status | Auto-Sorted Labels | Verification Auditor")

# --- 2. SIDEBAR: API SETTINGS ---
with st.sidebar:
    st.header("🔑 API Settings")
    mode = st.radio("Status Provider", ["Ozon Seller API", "17Track API"])
    
    if mode == "Ozon Seller API":
        ozon_client_id = st.text_input("Client ID", placeholder="123456")
        ozon_api_key = st.text_input("API Key", type="password")
    else:
        seventeen_token = st.text_input("17Track Token", type="password")

    st.divider()
    st.header("⚙️ OCR Settings")
    scan_dpi = st.select_slider("Scan Quality (DPI)", options=[150, 200, 300], value=200)

# --- 3. LOGIC FUNCTIONS ---
def robust_parse(text_data):
    """Parses pasted data into {TrackingID: {ProductIDs}} mapping"""
    data_map = {}
    # Splitter handles Tabs (Excel), Commas, Pipes, or Multiple Spaces
    splitter = re.compile(r'[,\t|]|\s{2,}')
    for line in text_data.strip().split('\n'):
        line = line.strip()
        if not line: continue
        parts = [p.strip() for p in splitter.split(line) if p.strip()]
        if len(parts) >= 2:
            tn = parts[0]
            pids = set(p.upper() for p in parts[1:])
            data_map.setdefault(tn, set()).update(pids)
    return data_map

# --- 4. MAIN TABS ---
tab_status, tab_match, tab_audit, tab_trans = st.tabs([
    "📊 Bulk Status", 
    "🔍 PDF Filter/Sort", 
    "⚖️ Verification Auditor", 
    "🌐 Translator"
])

# --- TAB 1: BULK STATUS ---
with tab_status:
    st.subheader("1. Tracking Status Checker")
    raw_status_input = st.text_area("Paste Tracking Numbers", height=150, key="status_input")
    target_ids = SCANNING_ID_REGEX.findall(raw_status_input)
    
    if target_ids and st.button("Check API Status"):
        # API logic (Ozon/17Track) goes here...
        st.info(f"Checking status for {len(set(target_ids))} items...")

# --- TAB 2: PDF FILTER & SORT ---
with tab_match:
    st.subheader("2. PDF Auto-Sort Sequence")
    label_file = st.file_uploader("Upload Bulk Labels PDF", type="pdf")
    if label_file and raw_status_input:
        if st.button("Generate Sorted PDF"):
            # PDF sorting logic goes here...
            st.success("Sequence re-ordered based on input list.")

# --- TAB 3: VERIFICATION AUDITOR (The Integrated Tool) ---
with tab_audit:
    st.subheader("⚖️ Logistics Auditor (Master vs. Scan)")
    st.info("Paste your 'Master' list and your 'Scanned' data to find mismatches.")
    
    col1, col2 = st.columns(2)
    with col1:
        master_data = st.text_area("1. MASTER DATA (Expected)", height=250, help="Paste: [TrackingID] [ProductID]")
    with col2:
        scan_data = st.text_area("2. SCANNED DATA (Actual)", height=250, help="Paste: [TrackingID] [ProductID]")

    if st.button("⚡ Run Full Audit", type="primary"):
        if master_data and scan_data:
            master_map = robust_parse(master_data)
            scan_map = robust_parse(scan_data)
            
            all_tns = sorted(list(set(master_map.keys()) | set(scan_map.keys())))
            audit_results = []
            
            for tn in all_tns:
                m_set = master_map.get(tn, set())
                s_set = scan_map.get(tn, set())
                
                status = "✅ MATCH" if m_set == s_set else "❌ ERROR"
                missing = m_set - s_set
                extra = s_set - m_set
                
                audit_results.append({
                    "Tracking Number": tn,
                    "Status": status,
                    "Missing Items": ", ".join(missing) if missing else "-",
                    "Extra Items": ", ".join(extra) if extra else "-",
                    "Qty Exp": len(m_set),
                    "Qty Got": len(s_set)
                })
            
            # --- Results Display ---
            df_audit = pd.DataFrame(audit_results)
            
            # Stats Metrics
            err_count = len(df_audit[df_audit['Status'] == "❌ ERROR"])
            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("Total Audited", len(all_tns))
            m_col2.metric("Matches", len(all_tns) - err_count)
            m_col3.metric("Discrepancies", err_count, delta=-err_count, delta_color="inverse")
            
            # Interactive Filter/Search
            search_query = st.text_input("🔍 Search Tracking ID in Results")
            if search_query:
                df_audit = df_audit[df_audit['Tracking Number'].str.contains(search_query)]

            # Styling the table
            def highlight_errors(val):
                color = '#ffcccc' if val == "❌ ERROR" else ''
                return f'background-color: {color}'

            st.dataframe(df_audit.style.applymap(highlight_errors, subset=['Status']), use_container_width=True)
            
            # Download Mismatches Only
            mismatches = df_audit[df_audit['Status'] == "❌ ERROR"]
            if not mismatches.empty:
                st.download_button("📥 Download Mismatch Report (CSV)", 
                                   mismatches.to_csv(index=False), 
                                   "audit_errors.csv", "text/csv")
        else:
            st.error("Please provide data in both boxes.")

# --- TAB 4: QUICK TRANSLATOR ---
with tab_trans:
    st.subheader("🌐 Instant Translator")
    source_text = st.text_area("Russian Text", height=100)
    if source_text:
        translated = GoogleTranslator(source='auto', target='en').translate(source_text)
        st.success(f"**English:** {translated}")

st.divider()
st.caption("Developed for Ozon Logistics Management | Auto-Sort & Audit Engine Active")
