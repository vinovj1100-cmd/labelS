import streamlit as st
import pytesseract
import pypdf, re, io
import requests
import pandas as pd
import altair as alt
from pdf2image import convert_from_bytes
from pyzbar.pyzbar import decode
from difflib import SequenceMatcher
from deep_translator import GoogleTranslator

# --- CONFIGURATION ---
OZON_API_URL = "https://api-seller.ozon.ru/v3/posting/fbs/list"
SCANNING_ID_REGEX = re.compile(r"\b\d{4,10}-?\d{4}-?\d?\b")

# --- SETUP ---
st.set_page_config(page_title="Ozon Master Tool", layout="wide", page_icon="📦")
st.title("📦 Ozon Master Tool: Sorter + Status")

# --- SIDEBAR: API SETTINGS ---
with st.sidebar:
    st.header("🔐 API Settings (For Status)")
    ozon_client_id = st.text_input("Client ID (Customer ID)", placeholder="123456")
    ozon_api_key = st.text_input("API Key", type="password", placeholder="Generated in Settings -> API Keys")
    
    if not ozon_api_key:
        st.warning("⚠ API Key needed for bulk checks.")
        st.markdown("[Get Key Here](https://seller.ozon.ru/app/settings/api-keys)")
    
    st.divider()
    st.header("⚙ Sorter Settings")
    scan_dpi = st.select_slider("Scan Quality (DPI)", options=[150, 200, 300], value=300)
    scan_area = st.radio("Scan Area", ["Top 1/3 (Fast)", "Full Page (Slow)"], index=0)

# --- SHARED INPUT SECTION ---
st.subheader("1. Input Tracking Numbers")
col_in1, col_in2 = st.columns([1, 2])

with col_in1:
    raw_input = st.text_area(
        "Paste Numbers Here",
        placeholder="12345678-0001-1\n98765432-0023-2",
        height=150,
        label_visibility="collapsed"
    )
    
    # Parse Inputs immediately
    target_ids = []
    if raw_input:
        target_ids = list(dict.fromkeys(SCANNING_ID_REGEX.findall(raw_input)))
        st.caption(f"✅ Detected {len(target_ids)} unique numbers")

# --- TABS FOR FUNCTIONS ---
tab_status, tab_sort = st.tabs(["📡 Bulk Status Check", "📄 Label Sorter PDF"])

# ==========================================
# TAB 1: BULK STATUS CHECKER (REAL-TIME)
# ==========================================
with tab_status:
    st.markdown("### Real-Time Order Status")
    
    if not target_ids:
        st.info("👈 Paste tracking numbers on the left to start.")
    elif not (ozon_client_id and ozon_api_key):
        st.error("🛑 API Key Missing. Cannot check bulk status.")
        st.markdown("**Why?** Cancellation reasons are private data. You must generate a Key in Ozon Seller -> Settings.")
    else:
        if st.button("📡 Check Status of All Orders", type="primary"):
            progress = st.progress(0)
            results = []
            
            # Batching (Ozon Limit is 100 per call)
            chunk_size = 100
            chunks = [target_ids[i:i + chunk_size] for i in range(0, len(target_ids), chunk_size)]
            
            headers = {
                "Client-Id": ozon_client_id,
                "Api-Key": ozon_api_key,
                "Content-Type": "application/json"
            }
            
            success = True
            
            for i, chunk in enumerate(chunks):
                payload = {
                    "filter": {"posting_number": chunk},
                    "dir": "ASC", "limit": 100, "offset": 0,
                    "with": {"analytics_data": False, "financial_data": False}
                }
                
                try:
                    response = requests.post(OZON_API_URL, json=payload, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        for posting in data.get('result', {}).get('postings', []):
                            status_raw = posting.get('status', 'unknown')
                            reason = "-"
                            
                            # Dig for cancellation reason
                            if status_raw == 'cancelled':
                                c = posting.get('cancellation', {})
                                reason = f"{c.get('cancellation_initiator', '?')}: {c.get('cancellation_type', '-')}"
                            
                            results.append({
                                "Tracking Number": posting.get('posting_number'),
                                "Status": status_raw.upper(),
                                "Ship Date": posting.get('shipment_date', '')[:10],
                                "Cancellation Reason": reason
                            })
                    elif response.status_code == 401:
                        st.error("❌ Authentication Failed: Check your Client ID and API Key.")
                        success = False
                        break
                    else:
                        st.error(f"API Error {response.status_code}: {response.text}")
                        
                except Exception as e:
                    st.error(f"Connection Error: {e}")
                
                progress.progress((i + 1) / len(chunks))
            
            if success and results:
                df = pd.DataFrame(results)
                
                # 1. Metrics Row
                m1, m2, m3 = st.columns(3)
                n_cancel = len(df[df['Status'] == 'CANCELLED'])
                n_deliv = len(df[df['Status'] == 'DELIVERED'])
                
                m1.metric("Total Checked", len(df))
                m2.metric("Cancelled", n_cancel, delta=-n_cancel, delta_color="inverse")
                m3.metric("Delivered", n_deliv, delta=n_deliv)
                
                # 2. Visualization (Donut Chart)
                chart_data = df['Status'].value_counts().reset_index()
                chart_data.columns = ['Status', 'Count']
                
                c = alt.Chart(chart_data).mark_arc(innerRadius=50).encode(
                    theta=alt.Theta(field="Count", type="quantitative"),
                    color=alt.Color(field="Status", type="nominal"),
                    tooltip=["Status", "Count"]
                )
                st.altair_chart(c, use_container_width=True)
                
                # 3. Detailed Dataframe with Highlights
                def color_row(row):
                    if row['Status'] == 'CANCELLED': return ['background-color: #ffcccc'] * len(row)
                    if row['Status'] == 'DELIVERED': return ['background-color: #ccffcc'] * len(row)
                    return [''] * len(row)

                st.dataframe(
                    df.style.apply(color_row, axis=1),
                    use_container_width=True,
                    column_config={
                        "Cancellation Reason": st.column_config.TextColumn("Reason", width="large")
                    }
                )
            elif success:
                st.warning("No data found. Are these valid Ozon FBS numbers?")

# ==========================================
# TAB 2: LABEL SORTER (PDF)
# ==========================================
with tab_sort:
    st.markdown("### PDF Label Sorter")
    label_file = st.file_uploader("Upload Labels PDF", type="pdf")
    
    if label_file and target_ids:
        if st.button("🔍 Sort PDF Labels"):
            status = st.empty()
            prog = st.progress(0)
            
            try:
                label_bytes = label_file.getvalue()
                
                # OPTIMIZATION: Crop Logic
                crop_h_factor = 3 if "Top 1/3" in scan_area else 1
                
                images = convert_from_bytes(label_bytes, dpi=scan_dpi)
                label_reader = pypdf.PdfReader(io.BytesIO(label_bytes))
                sorted_writer = pypdf.PdfWriter()
                
                page_map = {}
                matched_ids = set()
                
                # Scan Loop
                for i, img in enumerate(images):
                    status.text(f"Scanning page {i+1}...")
                    w, h = img.size
                    crop_img = img.crop((0, 0, w, h // crop_h_factor))
                    
                    # OCR + Barcode
                    ocr = pytesseract.image_to_string(crop_img)
                    bc = "".join([b.data.decode('utf-8') for b in decode(crop_img)])
                    found = set(SCANNING_ID_REGEX.findall(ocr + bc))
                    
                    # Normalize & Match
                    found_norm = {re.sub(r"[^0-9]", "", x) for x in found}
                    
                    for tid in target_ids:
                        tnorm = re.sub(r"[^0-9]", "", tid)
                        if tnorm in found_norm:
                            page_map[tnorm] = label_reader.pages[i]
                            matched_ids.add(tnorm)
                            
                    prog.progress((i + 1) / len(images))
                
                # Build Result
                if matched_ids:
                    for tid in target_ids:
                        tnorm = re.sub(r"[^0-9]", "", tid)
                        if tnorm in page_map:
                            sorted_writer.add_page(page_map[tnorm])
                            
                    res_pdf = io.BytesIO()
                    sorted_writer.write(res_pdf)
                    
                    st.success(f"Sorted {len(matched_ids)} labels!")
                    st.download_button("📥 Download Sorted PDF", res_pdf.getvalue(), "sorted.pdf", "application/pdf", type="primary")
                else:
                    st.error("No matches found.")
                    
            except Exception as e:
                st.error(f"Error: {e}")

