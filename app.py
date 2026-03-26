import streamlit as st
import pytesseract
import pypdf, re, io
import requests
import pandas as pd
from pdf2image import convert_from_bytes
from pyzbar.pyzbar import decode
from deep_translator import GoogleTranslator

# --- 1. CONFIGURATION ---
OZON_API_URL = "https://api-seller.ozon.ru"
SCANNING_ID_REGEX = re.compile(r"\b\d{4,10}-?\d{4}-?\d?\b")

st.set_page_config(page_title="Ozon Master Tool", layout="wide", page_icon="📦")
st.title("📦 Ozon Master Tool: Status & Barcode Matcher")

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
    st.header("⚙️ Scanner Settings")
    scan_dpi = st.select_slider("Scan Quality (DPI)", options=[100, 150, 200, 300], value=200)

# --- 3. SHARED INPUT SECTION ---
st.subheader("1. Input Your Target Tracking Numbers")
raw_input = st.text_area("Paste your list here (one per line or comma-separated)", placeholder="12345678-0001-1", height=120)
target_ids = []
if raw_input:
    target_ids = list(dict.fromkeys(SCANNING_ID_REGEX.findall(raw_input)))
    st.success(f"✅ Detected {len(target_ids)} unique target IDs")

# --- 4. API LOGIC FUNCTIONS ---
def fetch_17track(ids, token):
    headers = {"17token": token, "Content-Type": "application/json"}
    # Step 1: Register (Required)
    reg_payload = [{"number": tid} for tid in ids]
    requests.post("https://api.17track.net", json=reg_payload, headers=headers)
    # Step 2: Get Info
    response = requests.post("https://api.17track.net", json=reg_payload, headers=headers)
    results = []
    if response.status_code == 200:
        for item in response.json().get("data", {}).get("accepted", []):
            status_code = str(item.get("track_info", {}).get("latest_status", {}).get("status", "0"))
            status_map = {"30": "DELIVERED", "40": "CANCELLED/ISSUE"}
            results.append({
                "Tracking Number": item.get("number"),
                "Status": status_map.get(status_code, "IN TRANSIT"),
                "Last Event": item.get("track_info", {}).get("latest_status", {}).get("desc", "-")
            })
    return results

# --- 5. MAIN TABS ---
tab_status, tab_match, tab_trans = st.tabs(["📊 Bulk Status", "🔍 Barcode Matcher", "🌐 Quick Translator"])

with tab_status:
    if not target_ids:
        st.info("👈 Please paste tracking numbers above first.")
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
                st.dataframe(df.style.apply(lambda x: ['background-color: #ffcccc' if v in ['CANCELLED', 'CANCELLED/ISSUE'] else '' for v in x], axis=1), use_container_width=True)
                st.download_button("📥 Download Status CSV", df.to_csv(index=False), "status_report.csv", "text/csv")

with tab_match:
    st.markdown("### 📄 PDF Barcode Scanner")
    label_file = st.file_uploader("Upload Labels PDF to verify against your list", type="pdf")
    
    if label_file and target_ids:
        if st.button("🔍 Scan & Find Mismatches", type="primary"):
            with st.spinner("Decoding Barcodes from PDF..."):
                found_in_pdf = []
                images = convert_from_bytes(label_file.read(), dpi=scan_dpi)
                
                for img in images:
                    # 1. Try Barcode Decode
                    barcodes = decode(img)
                    for b in barcodes:
                        found_in_pdf.extend(SCANNING_ID_REGEX.findall(b.data.decode("utf-8")))
                    # 2. OCR Backup
                    if not barcodes:
                        found_in_pdf.extend(SCANNING_ID_REGEX.findall(pytesseract.image_to_string(img)))
                
                found_in_pdf = list(set(found_in_pdf))
                matched = [tid for tid in target_ids if tid in found_in_pdf]
                missing = [tid for tid in target_ids if tid not in found_in_pdf]
                extra = [fid for fid in found_in_pdf if fid not in target_ids]

                st.divider()
                m1, m2 = st.columns(2)
                with m1:
                    st.success(f"✅ Matched ({len(matched)})")
                    st.write(matched if matched else "None")
                with m2:
                    st.error(f"❌ Mismatches ({len(missing) + len(extra)})")
                    if missing: st.warning(f"Missing from PDF: {', '.join(missing)}")
                    if extra: st.info(f"Extra in PDF (Not in list): {', '.join(extra)}")

with tab_trans:
    st.markdown("### 🌐 Russian -> English Translator")
    source_text = st.text_area("Paste text to translate:", height=100)
    if source_text:
        translated = GoogleTranslator(source='auto', target='en').translate(source_text)
        st.success(f"**Translation:** {translated}")

st.caption("<<< VINO VJ - 17Track, Barcode Scanner & Translator Integrated >>>")
