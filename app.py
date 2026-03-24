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
st.title("📦 Label Sorter Pro")

# --- MAIN UI ---

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Enter Tracking Numbers")
    raw_input = st.text_area(
        "Paste IDs here",
        placeholder="Paste IDs here (one per line):\n1234-5678-0\n9876-5432-1",
        height=300,
        label_visibility="collapsed"
    )

with col2:
    st.subheader("2. Upload Labels PDF")
    label_file = st.file_uploader("Upload PDF", type="pdf", label_visibility="collapsed")

if label_file and raw_input:
    # Parse Inputs
    raw_targets = list(dict.fromkeys(SCANNING_ID_REGEX.findall(raw_input)))
    target_ids = raw_targets
    normalized_target_map = {normalize_id(t): t for t in target_ids}
    normalized_targets = set(normalized_target_map.keys())

    if st.button("🔍 Start Sorting Labels", use_container_width=True):
        status = st.empty()
        progress_bar = st.progress(0)
        
        try:
            # Load PDF
            label_bytes = label_file.getvalue()
            images = convert_from_bytes(label_bytes, dpi=200)
            label_reader = pypdf.PdfReader(io.BytesIO(label_bytes))
            
            sorted_writer = pypdf.PdfWriter()
            page_map = {}
            matched_ids = set()
            candidate_to_page = {}

            # 1. SCANNING PHASE
            for i, img in enumerate(images):
                status.text(f"Scanning label page {i+1} of {len(images)}...")

                # OCR & Barcode Reading
                ocr_text_raw = pytesseract.image_to_string(img)
                bc_text_raw = "".join([bc.data.decode('utf-8') for bc in decode(img)])

                found_ids = {normalize_id(x) for x in SCANNING_ID_REGEX.findall(ocr_text_raw + bc_text_raw)}

                for fid in found_ids:
                    candidate_to_page.setdefault(fid, i)

                for normalized_target in normalized_targets:
                    if normalized_target in found_ids:
                        page_map[normalized_target] = label_reader.pages[i]
                        matched_ids.add(normalized_target)

                progress_bar.progress((i + 1) / len(images))

            # 2. FUZZY MATCHING PHASE
            fuzzy_matches = {}
            FUZZY_THRESHOLD = 0.88
            unmatched_normalized = [n for n in normalized_targets if n not in matched_ids]
            
            for unm in unmatched_normalized:
                best_score = 0.0
                best_cand = None
                for cand in candidate_to_page.keys():
                    score = SequenceMatcher(None, unm, cand).ratio()
                    if score > best_score:
                        best_score = score
                        best_cand = cand

                if best_cand is not None and best_score >= FUZZY_THRESHOLD:
                    matched_ids.add(unm)
                    page_map[unm] = label_reader.pages[candidate_to_page[best_cand]]
                    fuzzy_matches[unm] = (best_cand, best_score)

            # 3. ASSEMBLY & RESULTS
            final_unmatched = [normalized_target_map[n] for n in normalized_targets if n not in matched_ids]
            
            status.success("Processing Complete!")
            st.divider()

            # Results Tabs
            tab_match, tab_miss = st.tabs([
                f"✅ Sorted Results ({len(matched_ids)})", 
                f"⚠️ Review Mismatches ({len(final_unmatched)})"
            ])

            with tab_match:
                if matched_ids:
                    # Build final PDF
                    for tid in target_ids:
                        nid = normalize_id(tid)
                        if nid in page_map:
                            sorted_writer.add_page(page_map[nid])
                    
                    res_pdf = io.BytesIO()
                    sorted_writer.write(res_pdf)
                    
                    st.download_button(
                        label="📥 Download Sorted PDF",
                        data=res_pdf.getvalue(),
                        file_name="SORTED_LABELS.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
                else:
                    st.warning("No matches found.")

                if fuzzy_matches:
                    st.info(f"⚡ Fuzzy matched {len(fuzzy_matches)} IDs (threshold {int(FUZZY_THRESHOLD*100)}%):")
                    for unm, (cand, score) in fuzzy_matches.items():
                        st.text(f"{normalized_target_map[unm]} -> {cand}")

            with tab_miss:
                if final_unmatched:
                    st.error("The following IDs were NOT found in the PDF:")
                    st.code("\n".join(final_unmatched))
                    st.caption("Tip: Check if the PDF is blurry or if these IDs have a different format.")
                else:
                    st.balloons()
                    st.success("100% Match! No errors to review.")

        except Exception as e:
            st.error(f"System Error: {e}")

# --- UTILITY: QUICK TRANSLATOR ---
st.markdown("---")
with st.expander("🌍 Quick Translator (Any Language -> English)", expanded=True):
    tr_col1, tr_col2 = st.columns(2)
    
    with tr_col1:
        source_text = st.text_area("Paste foreign text here:", height=100)
    
    with tr_col2:
        st.markdown("**English Translation:**")
        if source_text:
            try:
                translated = GoogleTranslator(source='auto', target='en').translate(source_text)
                st.info(translated)
            except Exception as e:
                st.warning("⚠️ Translation requires internet connection.")
        else:
            st.caption("Waiting for input...")

st.caption("<<< VINO VJ >>>")
