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
st.title("📦 Ozon Master Tool: Status & Auto-Sorted Labels")

# --- 2. SIDEBAR: API SETTINGS ---
with st.sidebar:
    st.header("🔑 API Settings")
    mode = st.radio("Status Provider", ["Ozon Seller API", "17Track API"])
    
    if mode == "Ozon Seller API":
        ozon_client_id = st.text_input("Client ID", placeholder="123456")
        ozon_api_key = st.text_input("API Key", type="password")
    else:
        seventeen_token = st.text_input("17Track Token (17token)", type="password")
        st.markdown("[Get 17Track Token](https://api.17track.net)")

    st.divider()
    st.header("⚙️ Scanner Settings")
    scan_dpi = st.select_slider("Scan Quality (DPI)", options=[150, 200, 300], value=200)

# --- 3. SHARED INPUT SECTION ---
st.subheader("1. Input Your Target Tracking Numbers")
raw_input = st.text_area("Paste your list here in the ORDER you want to print", placeholder="12345678-0001-1", height=150)
target_ids = []
if raw_input:
    # Maintain order from the text area while removing duplicates
    seen = set()
    target_ids = [x for x in SCANNING_ID_REGEX.findall(raw_input) if not (x in seen or seen.add(x))]
    st.success(f"✅ Detected {len(target_ids)} unique target IDs in sequence")

# --- 4. API LOGIC FUNCTIONS ---
def fetch_17track(ids, token):
    headers = {"17token": token, "Content-Type": "application/json"}
    reg_payload = [{"number": tid} for tid in ids]
    requests.post("https://api.17track.net", json=reg_payload, headers=headers)
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
tab_status, tab_match, tab_trans = st.tabs(["📊 Bulk Status", "🔍 Auto-Sorted PDF Filter", "🌐 Quick Translator"])

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
    st.markdown("### 📄 Filter & Auto-Sort PDF")
    label_file = st.file_uploader("Upload Labels PDF (Bulk)", type="pdf")
    
    if label_file and target_ids:
        if st.button("🔍 Scan, Sort & Generate PDF", type="primary"):
            with st.spinner("Mapping PDF pages and re-ordering..."):
                pdf_reader = pypdf.PdfReader(io.BytesIO(label_file.getvalue()))
                pdf_writer = pypdf.PdfWriter()
                images = convert_from_bytes(label_file.getvalue(), dpi=scan_dpi)
                
                # Map Tracking_ID to the actual PDF page object
                id_to_page_map = {}
                
                for i, img in enumerate(images):
                    page_codes = []
                    # Try Barcode Decode
                    barcodes = decode(img)
                    for b in barcodes:
                        page_codes.extend(SCANNING_ID_REGEX.findall(b.data.decode("utf-8")))
                    # OCR Fallback
                    if not barcodes:
                        page_codes.extend(SCANNING_ID_REGEX.findall(pytesseract.image_to_string(img)))
                    
                    # Store mapping
                    for code in page_codes:
                        id_to_page_map[code] = pdf_reader.pages[i]

                # Re-build PDF in the sequence of 'target_ids'
                matched_count = 0
                for tid in target_ids:
                    if tid in id_to_page_map:
                        pdf_writer.add_page(id_to_page_map[tid])
                        matched_count += 1

                if matched_count == 0:
                    st.error("No matches found. Ensure IDs in the PDF match your pasted list.")
                else:
                    out_io = io.BytesIO()
                    pdf_writer.write(out_io)
                    st.success(f"✅ Created PDF with {matched_count} pages sorted exactly like your list.")
                    st.download_button("📥 Download SORTED_LABELS.pdf", out_io.getvalue(), "sorted_labels.pdf", "application/pdf")
                    
                    # Show Mismatches
                    missing = [tid for tid in target_ids if tid not in id_to_page_map]
                    if missing:
                        st.warning(f"**Missing from PDF ({len(missing)}):** {', '.join(missing)}")

with tab_trans:
    st.markdown("### 🌐 Quick Translator")
    source_text = st.text_area("Paste text (e.g., Russian) to translate:", height=100)
    if source_text:
        translated = GoogleTranslator(source='auto', target='en').translate(source_text)
        st.success(f"**Translation:** {translated}")

st.caption("<<< VINO VJ - Auto-Sort Sequence Active >>>")
