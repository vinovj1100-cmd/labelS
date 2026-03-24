import streamlit as st
import pytesseract
import pypdf, re, io
from pdf2image import convert_from_bytes
from pyzbar.pyzbar import decode
from difflib import SequenceMatcher
from deep_translator import GoogleTranslator

# --- UTILS ---
SCANNING_ID_REGEX = re.compile(r"\b\d{4,10}-?\d{4}-?\d?\b")

def normalize_id(raw_id: str) -> str:
    return re.sub(r"[^0-9]", "", raw_id)

# --- SYSTEM SETUP ---
st.set_page_config(page_title="Label Sorter Pro", layout="wide")

# Sidebar Language Selector
st.sidebar.header("Settings")
lang_options = list(TRANSLATIONS.keys())
selected_lang = st.sidebar.selectbox("Language / Idioma", lang_options)
T = TRANSLATIONS[selected_lang]

# --- MAIN TOOL: LABEL SORTER ---
st.title(T["title"])

col1, col2 = st.columns([1, 1])
with col1:
    st.subheader(T["step1"])
    raw_input = st.text_area(T["step1"], placeholder=T["placeholder"], height=200, label_visibility="collapsed")
with col2:
    st.subheader(T["step2"])
    label_file = st.file_uploader("Upload PDF", type="pdf", label_visibility="collapsed")

if label_file and raw_input:
    if st.button(T["btn_start"], use_container_width=True):
        # [Existing Logic: OCR, Matching, PDF Build]
        try:
            # ... (Logic condensed for brevity, same as previous version) ...
            # 1. Setup
            target_ids = list(dict.fromkeys(SCANNING_ID_REGEX.findall(raw_input)))
            normalized_target_map = {normalize_id(t): t for t in target_ids}
            normalized_targets = set(normalized_target_map.keys())
            
            label_bytes = label_file.getvalue()
            images = convert_from_bytes(label_bytes, dpi=200)
            label_reader = pypdf.PdfReader(io.BytesIO(label_bytes))
            sorted_writer = pypdf.PdfWriter()
            
            page_map, matched_ids, cand_to_page = {}, set(), {}

            # 2. Scan
            progress = st.progress(0)
            for i, img in enumerate(images):
                ocr_txt = pytesseract.image_to_string(img)
                bc_txt = "".join([b.data.decode('utf-8') for b in decode(img)])
                found = {normalize_id(x) for x in SCANNING_ID_REGEX.findall(ocr_txt + bc_txt)}
                
                for fid in found: cand_to_page.setdefault(fid, i)
                for nt in normalized_targets:
                    if nt in found:
                        page_map[nt] = label_reader.pages[i]
                        matched_ids.add(nt)
                progress.progress((i+1)/len(images))

            # 3. Fuzzy Match
            unmatched = [n for n in normalized_targets if n not in matched_ids]
            for unm in unmatched:
                best_c, best_s = None, 0.0
                for cand in cand_to_page:
                    s = SequenceMatcher(None, unm, cand).ratio()
                    if s > best_s: best_c, best_s = cand, s
                if best_c and best_s > 0.88:
                    matched_ids.add(unm)
                    page_map[unm] = label_reader.pages[cand_to_page[best_c]]

            # 4. Results
            st.divider()
            tab_yes, tab_no = st.tabs([f"{T['tab_sorted']} ({len(matched_ids)})", f"{T['tab_review']}"])
            
            with tab_yes:
                if matched_ids:
                    for tid in target_ids:
                        if normalize_id(tid) in page_map: sorted_writer.add_page(page_map[normalize_id(tid)])
                    out_pdf = io.BytesIO()
                    sorted_writer.write(out_pdf)
                    st.download_button("📥 Download PDF", out_pdf.getvalue(), "SORTED.pdf", "application/pdf", type="primary")
            
            with tab_no:
                missing = [normalized_target_map[n] for n in normalized_targets if n not in matched_ids]
                if missing: st.error("Missing IDs:"); st.code("\n".join(missing))
                else: st.success("All matched!")

        except Exception as e:
            st.error(f"Error: {e}")

# --- NEW FEATURE: TRANSLATOR UTILITY ---
st.markdown("---")
with st.expander(T["util_title"], expanded=True):
    tr_col1, tr_col2 = st.columns(2)
    
    with tr_col1:
        # Left Column: Input
        source_text = st.text_area(T["trans_input"], height=150)
    
    with tr_col2:
        # Right Column: Output
        st.markdown(f"**{T['trans_output']}**")
        if source_text:
            try:
                # Uses Google Translate backend (No API key needed)
                translated = GoogleTranslator(source='auto', target='en').translate(source_text)
                st.info(translated)
            except Exception as e:
                st.warning("⚠️ Translation requires internet connection.")
                st.caption(str(e))
        else:
            st.caption("Waiting for text...")

st.caption("<<< VINO VJ >>>")
