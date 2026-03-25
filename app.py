import streamlit as st
import pytesseract
import pypdf, re, io
import requests
import pandas as pd
import altair as alt
from pdf2image import convert_from_bytes
from pyzbar.pyzbar import decode
from deep_translator import GoogleTranslator

# --- 1. CONFIGURATION ---
OZON_API_URL = "https://api-seller.ozon.ru"
SCANNING_ID_REGEX = re.compile(r"\b\d{4,10}-?\d{4}-?\d?\b")

st.set_page_config(page_title="Ozon Master Tool", layout="wide", page_icon="📦")
st.title("📦 Ozon Master Tool: Sorter + Status")

# --- 2. SIDEBAR: API SETTINGS ---
with st.sidebar:
    st.header("🔑 API Settings")
    mode = st.radio("Status Provider", ["Ozon Seller API", "17Track API"])
    
    if mode == "Ozon Seller API":
        ozon_client_id = st.text_input("Client ID", placeholder="123456")
        ozon_api_key = st.text_input("API Key", type="password")
        st.markdown("[Get Ozon Key](https://seller.ozon.ru)")
    else:
        seventeen_token = st.text_input("17Track Token (17token)", type="password")
        st.markdown("[Get 17Track Token](https://api.17track.net)")

    st.divider()
    st.header("⚙️ Sorter Settings")
    scan_dpi = st.select_slider("Scan Quality (DPI)", options=[150, 200, 300], value=200)
    scan_area = st.radio("Scan Area", ["Top 1/3 (Fast)", "Full Page (Slow)"], index=0)

# --- 3. SHARED INPUT SECTION ---
st.subheader("1. Input Tracking Numbers")
col_in1, col_in2 = st.columns([1, 2])

with col_in1:
    raw_input = st.text_area("Paste Numbers Here", placeholder="12345678-0001-1", height=150)
    target_ids = []
    if raw_input:
        target_ids = list(dict.fromkeys(SCANNING_ID_REGEX.findall(raw_input)))
        st.caption(f"✅ Detected {len(target_ids)} unique numbers")

# --- 4. 17TRACK API LOGIC ---
def fetch_17track(ids, token):
    headers = {"17token": token, "Content-Type": "application/json"}
    # 17Track requires registration before tracking
    reg_payload = [{"number": tid} for tid in ids]
    requests.post("https://api.17track.net", json=reg_payload, headers=headers)
    
    response = requests.post("https://api.17track.net", json=reg_payload, headers=headers)
    results = []
    if response.status_code == 200:
        for item in response.json().get("data", {}).get("accepted", []):
            status_code = str(item.get("track_info", {}).get("latest_status", {}).get("status", "0"))
            # 30=Delivered, 40=Cancelled/Issue
            status_map = {"30": "DELIVERED", "40": "CANCELLED/ISSUE"}
            results.append({
                "Tracking Number": item.get("number"),
                "Status": status_map.get(status_code, "IN TRANSIT"),
                "Last Event": item.get("track_info", {}).get("latest_status", {}).get("desc", "-")
            })
    return results

# --- 5. TABS ---
tab_status, tab_sort = st.tabs(["📊 Bulk Status Check", "📄 Label Sorter PDF"])

with tab_status:
    if not target_ids:
        st.info("👈 Paste tracking numbers on the left to start.")
    else:
        if st.button(f"Check Status via {mode}", type="primary"):
            results = []
            if mode == "Ozon Seller API" and ozon_api_key and ozon_client_id:
                headers = {"Client-Id": ozon_client_id, "Api-Key": ozon_api_key, "Content-Type": "application/json"}
                payload = {"filter": {"posting_number": target_ids}, "limit": 100}
                res = requests.post(OZON_API_URL, json=payload, headers=headers)
                if res.status_code == 200:
                    for p in res.json().get('result', {}).get('postings', []):
                        reason = "-"
                        if p.get('status') == 'cancelled':
                            c = p.get('cancellation', {})
                            reason = f"{c.get('cancellation_initiator')}: {c.get('cancellation_type')}"
                        results.append({"Tracking Number": p.get('posting_number'), "Status": p.get('status').upper(), "Details": reason})
            elif mode == "17Track API" and seventeen_token:
                results = fetch_17track(target_ids, seventeen_token)
            
            if results:
                df = pd.DataFrame(results)
                # Highlight Canceled rows in pink
                def highlight_cancel(row):
                    return ['background-color: #ffcccc' if row['Status'] in ['CANCELLED', 'CANCELLED/ISSUE'] else '' for _ in row]
                
                st.dataframe(df.style.apply(highlight_cancel, axis=1), use_container_width=True)
                st.download_button("📥 Download Results (CSV)", df.to_csv(index=False), "ozon_report.csv", "text/csv")

with tab_sort:
    st.markdown("### PDF Label Sorter")
    label_file = st.file_uploader("Upload Labels PDF", type="pdf")
    if label_file and target_ids:
        if st.button("Sort PDF Labels"):
            # Existing OCR sorting logic would go here
            st.write("Scanning and sorting labels...")
st.markdown("---")
# --- 6. QUICK TRANSLATOR (FROM YOUR IMAGE) ---
st.markdown("---")
with st.expander("🌐 Quick Translator (Any Language -> English)", expanded=True):
    tr_col1, tr_col2 = st.columns(2)
    
    with tr_col1:
        source_text = st.text_area("Paste foreign text here (e.g., Russian cancellation reason):", height=100)
    
    with tr_col2:
        st.markdown("**English Translation:**")
        if source_text:
            try:
                translated = GoogleTranslator(source='auto', target='en').translate(source_text)
                st.info(translated)
            except Exception as e:
                st.warning("Translation requires internet connection.")
        else:
            st.caption("Waiting for input...")

st.caption("<<< VINO VJ - 17Track & Translator Integrated >>>")
