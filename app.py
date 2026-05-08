import streamlit as st
import pytesseract
import pypdf, re, io
import requests
import pandas as pd
from pdf2image import convert_from_bytes
from pyzbar.pyzbar import decode
from deep_translator import GoogleTranslator

# --- 1. CONFIGURATION & REGEX ---
# Specifically tuned for Ozon Posting Numbers: 12345678-0001-1
SCANNING_ID_REGEX = re.compile(r"\b\d{4,12}-?\d{4}-?\d?\b")

st.set_page_config(page_title="Ozon Master Tool Pro", layout="wide", page_icon="📦")

# Professional UI Styling
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e1e4e8; }
    div[data-testid="stExpander"] { background-color: #ffffff; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIC ENGINES ---

def robust_parse_ozon_multiline(text_data):
    """
    Groups multi-line product descriptions with their tracking numbers.
    Perfect for data pasted directly from Ozon Seller tables.
    """
    data_map = {}
    current_tn = None
    lines = text_data.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Search for a Tracking Number in the line
        tn_match = SCANNING_ID_REGEX.search(line)
        
        if tn_match:
            current_tn = tn_match.group()
            # Remove the ID from the line to get any same-line description
            product_desc = line.replace(current_tn, "").strip().strip('|').strip()
            data_map.setdefault(current_tn, set())
            if product_desc:
                data_map[current_tn].add(product_desc)
        elif current_tn:
            # Add line as a description to the current active Tracking Number
            data_map[current_tn].add(line)
            
    return data_map

# --- 3. SIDEBAR: GLOBAL SETTINGS ---

with st.sidebar:
    st.image("https://icons8.com", width=80)
    st.title("Settings")
    
    st.subheader("🛰 API Provider")
    api_mode = st.radio("Provider", ["Ozon Seller API", "17Track API"])
    
    st.divider()
    
    st.subheader("📷 PDF Scanner")
    scan_dpi = st.select_slider("Resolution (DPI)", options=[150, 200, 300], value=200, 
                                help="300 is slowest but most accurate for small barcodes.")
    
    st.divider()
    st.caption("v5.5 Build | Ozon Auditor Engine")

# --- 4. MAIN INTERFACE ---

st.title("📦 Ozon Master Tool Pro")
tabs = st.tabs(["📊 Bulk Status", "🔍 PDF Filter/Sort", "⚖️ Verification Auditor", "🌐 Translator"])

# --- TAB 1: BULK STATUS ---
with tabs[0]:
    st.subheader("1. Real-time Tracking Status")
    status_input = st.text_area("Paste Tracking Numbers here", height=150, placeholder="Example: 81252745-0077-1")
    if st.button("Check Status", type="primary"):
        target_ids = SCANNING_ID_REGEX.findall(status_input)
        if target_ids:
            st.info(f"Connecting to {api_mode} for {len(set(target_ids))} items...")
        else:
            st.error("No valid Tracking Numbers detected.")

# --- TAB 2: PDF FILTER & SORT ---
with tabs[1]:
    st.subheader("2. Smart PDF Label Sequencer")
    col_a, col_b = st.columns([1, 2])
    
    with col_a:
        sort_input = st.text_area("Order List (Pasted Tracking IDs)", height=300, 
                                  placeholder="Paste the sequence you want to print...")
    with col_b:
        label_file = st.file_uploader("Upload Bulk PDF Labels", type="pdf")
        
    if label_file and sort_input:
        if st.button("🚀 Start Sequence Sorting"):
            target_ids = SCANNING_ID_REGEX.findall(sort_input)
            with st.spinner("Scanning and Re-ordering PDF..."):
                try:
                    pdf_reader = pypdf.PdfReader(io.BytesIO(label_file.getvalue()))
                    pdf_writer = pypdf.PdfWriter()
                    images = convert_from_bytes(label_file.getvalue(), dpi=scan_dpi)
                    
                    id_to_page_map = {}
                    for i, img in enumerate(images):
                        # Detect Barcodes
                        found = [b.data.decode("utf-8") for b in decode(img)]
                        # Fallback to OCR
                        if not found:
                            found = SCANNING_ID_REGEX.findall(pytesseract.image_to_string(img))
                        
                        for code in found:
                            # Clean code to match input format
                            clean_code = SCANNING_ID_REGEX.search(code)
                            if clean_code:
                                id_to_page_map[clean_code.group()] = pdf_reader.pages[i]

                    # Rebuild PDF in Order
                    matched = 0
                    for tid in target_ids:
                        if tid in id_to_page_map:
                            pdf_writer.add_page(id_to_page_map[tid])
                            matched += 1
                    
                    if matched > 0:
                        out = io.BytesIO()
                        pdf_writer.write(out)
                        st.success(f"✅ Created sorted PDF with {matched} pages.")
                        st.download_button("📥 Download Sorted PDF", out.getvalue(), "sorted_labels.pdf")
                    else:
                        st.error("Could not find any matching labels in the PDF.")
                except Exception as e:
                    st.error(f"Error processing PDF: {e}")

# --- TAB 3: VERIFICATION AUDITOR ---
with tabs[2]:
    st.subheader("3. Verification Auditor (Master vs Scan)")
    st.write("Ensures the correct products are being packed for each order.")
    
    col_left, col_right = st.columns(2)
    with col_left:
        master_raw = st.text_area("MASTER DATA (Expected)", height=300, key="m_audit")
    with col_right:
        scan_raw = st.text_area("SCANNED DATA (Actual)", height=300, key="s_audit")

    if st.button("⚡ Run Discrepancy Analysis", type="primary"):
        if master_raw and scan_raw:
            master_map = robust_parse_ozon_multiline(master_raw)
            scan_map = robust_parse_ozon_multiline(scan_raw)
            
            all_ids = sorted(list(set(master_map.keys()) | set(scan_map.keys())))
            results = []
            
            for tid in all_ids:
                exp = master_map.get(tid, set())
                got = scan_map.get(tid, set())
                
                # Check for Match
                status = "✅ MATCH" if exp == got else "❌ ERROR"
                missing = exp - got
                extra = got - exp
                
                results.append({
                    "Tracking ID": tid,
                    "Status": status,
                    "Missing Items": " | ".join(missing) if missing else "-",
                    "Extra Items": " | ".join(extra) if extra else "-",
                    "Total Exp": len(exp),
                    "Total Got": len(got)
                })
            
            # --- Results Presentation ---
            df = pd.DataFrame(results)
            err_count = len(df[df["Status"] == "❌ ERROR"])
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Orders Checked", len(all_ids))
            m2.metric("Perfect Matches", len(all_ids) - err_count)
            m3.metric("Errors Found", err_count, delta=-err_count, delta_color="inverse")
            
            # Search Tool
            search = st.text_input("🔍 Search Tracking ID in Results")
            if search:
                df = df[df["Tracking ID"].str.contains(search)]
                
            st.dataframe(df.style.apply(lambda x: ['background-color: #ffcccc' if v == "❌ ERROR" else '' for v in x], axis=1, subset=["Status"]), use_container_width=True)
            
            # Export Errors
            if err_count > 0:
                errors_only = df[df["Status"] == "❌ ERROR"]
                st.download_button("📥 Download Error Report (CSV)", errors_only.to_csv(index=False), "audit_errors.csv")
        else:
            st.warning("Please paste data into both Master and Scan fields.")

# --- TAB 4: QUICK TRANSLATOR ---
with tabs[3]:
    st.subheader("4. Logistic Content Translator")
    input_text = st.text_area("Paste Russian descriptions to translate", height=150)
    if input_text:
        with st.spinner("Translating..."):
            translated = GoogleTranslator(source='auto', target='en').translate(input_text)
            st.success("English Translation:")
            st.write(translated)

st.divider()
st.caption("Ozon Auditor v5.5 | Pro Warehouse Logistics Suite")
