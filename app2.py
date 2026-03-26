import streamlit as st
import pytesseract
import pypdf, re, io
from pdf2image import convert_from_bytes
from pyzbar.pyzbar import decode
from difflib import SequenceMatcher

# --- UTILS ---

SCANNING_ID_REGEX = re.compile(r"\b\d{4,10}-?\d{4}-?\d?\b")


def normalize_id(raw_id: str) -> str:
    return re.sub(r"[^0-9]", "", raw_id)


def extract_ids_from_text(text: str) -> set:
    return {normalize_id(x) for x in SCANNING_ID_REGEX.findall(text)}


# --- SYSTEM SETUP ---

st.set_page_config(page_title="Label Sorter Pro", layout="wide")
st.title("📦 Label Sorter (Paste & Match)")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Enter Tracking Numbers")
    raw_input = st.text_area(
        "Paste IDs here (one per line):",
        placeholder="1234-5678-0\n9876-5432-1",
        height=300
    )

with col2:
    st.subheader("2. Upload Labels PDF")
    label_file = st.file_uploader("Select the PDF containing the labels", type="pdf")

if label_file and raw_input:
    # Extract unique IDs from input (preserve user order, dedupe)
    raw_targets = list(dict.fromkeys(SCANNING_ID_REGEX.findall(raw_input)))
    target_ids = raw_targets
    normalized_target_map = {normalize_id(t): t for t in target_ids}
    normalized_targets = set(normalized_target_map.keys())

    if st.button("🔍 Start Sorting Labels", use_container_width=True):
        status = st.empty()
        progress_bar = st.progress(0)
        
        try:
            label_bytes = label_file.getvalue()
            images = convert_from_bytes(label_bytes, dpi=200)
            label_reader = pypdf.PdfReader(io.BytesIO(label_bytes))
            
            sorted_writer = pypdf.PdfWriter()
            page_map = {}
            matched_ids = set()  # normalized IDs found
            candidate_to_page = {}

            for i, img in enumerate(images):
                status.text(f"Scanning label page {i+1} of {len(images)}...")

                # Extract text and barcodes
                ocr_text_raw = pytesseract.image_to_string(img)
                bc_text_raw = "".join([bc.data.decode('utf-8') for bc in decode(img)])

                ocr_ids = extract_ids_from_text(ocr_text_raw)
                bc_ids = extract_ids_from_text(bc_text_raw)
                found_ids = ocr_ids.union(bc_ids)

                for fid in found_ids:
                    candidate_to_page.setdefault(fid, i)

                for normalized_target in normalized_targets:
                    if normalized_target in found_ids:
                        page_map[normalized_target] = label_reader.pages[i]
                        matched_ids.add(normalized_target)
                        # We don't break here in case one page has multiple IDs

                progress_bar.progress((i + 1) / len(images))

            # --- RESULTS SECTION ---
            st.divider()

            # Fuzzy match unmatched IDs if an OCR candidate is close
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

            unmatched_normalized = [n for n in normalized_targets if n not in matched_ids]
            unmatched_ids = [normalized_target_map[n] for n in [normalize_id(t) for t in target_ids] if n in unmatched_normalized]

            if matched_ids:
                # Build the PDF in the exact order of the pasted list
                for tid in target_ids:
                    normalized_tid = normalize_id(tid)
                    if normalized_tid in page_map:
                        sorted_writer.add_page(page_map[normalized_tid])

                res_pdf = io.BytesIO()
                sorted_writer.write(res_pdf)
                
                st.success(f"✅ Matched {len(matched_ids)} / {len(target_ids)} labels!")
                st.download_button(
                    "📥 Download Sorted PDF",
                    data=res_pdf.getvalue(),
                    file_name="SORTED_LABELS.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            # --- FUZZY MATCH REPORT ---
            if fuzzy_matches:
                st.info(f"⚡ Fuzzy matched {len(fuzzy_matches)} unmatched IDs (threshold {int(FUZZY_THRESHOLD*100)}%):")
                fuzzy_lines = [f"{normalized_target_map[unm]} -> {cand} ({score:.2f})" for unm, (cand, score) in fuzzy_matches.items()]
                st.code("\n".join(fuzzy_lines))

            # --- UNMATCHED IDS DISPLAY ---
            if unmatched_ids:
                st.error(f"❌ {len(unmatched_ids)} IDs were NOT found:")
                # Display unmatched IDs in a code block for easy copying
                st.code("\n".join(unmatched_ids))
                st.warning("Tip: These might be blurry in the PDF or use a different ID format.")

        except Exception as e:
            st.error(f"Error: {e}")

st.divider()
st.caption("<<< VINO VJ >>>")
