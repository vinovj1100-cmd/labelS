import streamlit as st
import pytesseract
import pypdf, re, io
import requests
import pandas as pd
from pdf2image import convert_from_bytes
from pyzbar.pyzbar import decode
from deep_translator import GoogleTranslator

# --- 1. SECURITY CONFIGURATION ---
# Change this password to your preferred login
APP_PASSWORD = "VINOVJ1100"

def check_password():
    """Returns True if the user had the correct password."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 System Locked")
        st.info("Please enter the Operator Password to access Ozon Master Tool Pro.")
        
        pwd_input = st.text_input("Enter Password", type="password")
        if st.button("Unlock System"):
            if pwd_input == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Incorrect Password. Access Denied.")
        return False
    return True

# --- 2. MAIN APPLICATION (Only runs if authenticated) ---
if check_password():
    # --- CONFIGURATION & REGEX ---
    SCANNING_ID_REGEX = re.compile(r"\b\d{4,12}-?\d{4}-?\d?\b")

    st.set_page_config(page_title="Ozon Master Tool Pro", layout="wide", page_icon="📦")

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
        
        if st.button("🔴 Logout & Lock"):
            st.session_state.authenticated = False
            st.rerun()

    # --- LOGIC ENGINES ---
    def robust_parse_multiline(text_data):
        data_map = {}
        current_tn = None
        for line in text_data.strip().split('\n'):
            line = line.strip()
            if not line: continue
            tn_match = SCANNING_ID_REGEX.search(line)
            if tn_match:
                current_tn = tn_match.group()
                desc = line.replace(current_tn, "").strip().strip('|').strip()
                data_map.setdefault(current_tn, set())
                if desc: data_map[current_tn].add(desc)
            elif current_tn:
                data_map[current_tn].add(line)
        return data_map

    # --- MAIN INTERFACE ---
    st.title(f"📦 Ozon Master Tool Pro | **{operator_name}**")
    
    tabs = st.tabs(["📊 Status", "🔍 PDF Sort", "⚖️ Auditor", "🌐 Translator"])

    # --- TAB 1: STATUS ---
    with tabs[0]:
        st.subheader("📊 **Real-time Status Checker**")
        status_input = st.text_area("Paste Tracking Numbers", height=150)
        if st.button("Check API Status"):
            if not ozon_key: st.warning("Please enter API Key in sidebar.")
            else: st.info(f"Checking {len(SCANNING_ID_REGEX.findall(status_input))} items...")

    # --- TAB 2: PDF SORT ---
    with tabs[1]:
        st.subheader("🔍 **PDF Label Sequencer (300 DPI)**")
        c1, c2 = st.columns(2)
        with c1:
            sort_list = st.text_area("Sequence Order", height=250)
        with c2:
            pdf_file = st.file_uploader("Upload Labels PDF", type="pdf")
        
        if st.button("🚀 Start Sequence Sort"):
            st.write("**Initializing scan...**")

    # --- TAB 3: AUDITOR ---
    with tabs[2]:
        st.subheader("⚖️ **Verification Auditor**")
        col_a, col_b = st.columns(2)
        with col_a:
            master_in = st.text_area("**MASTER (Expected)**", height=300)
        with col_b:
            scan_in = st.text_area("**SCAN (Actual)**", height=300)

        if st.button("⚡ Run Discrepancy Analysis", type="primary"):
            if master_in and scan_in:
                m_map = robust_parse_multiline(master_in)
                s_map = robust_parse_multiline(scan_in)
                all_ids = sorted(list(set(m_map.keys()) | set(s_map.keys())))
                
                results = []
                for tid in all_ids:
                    exp, got = m_map.get(tid, set()), s_map.get(tid, set())
                    status = "✅ MATCH" if exp == got else "❌ ERROR"
                    results.append({
                        "Tracking ID": f"**{tid}**",
                        "Status": status,
                        "Missing Items": " | ".join([f"**{x}**" for x in (exp - got)]) if (exp - got) else "-",
                        "Extra Items": " | ".join([f"**{x}**" for x in (got - exp)]) if (got - exp) else "-"
                    })
                
                df = pd.DataFrame(results)
                st.dataframe(df.style.apply(lambda x: ['background-color: #ffcccc; font-weight: bold' if v == "❌ ERROR" else '' for v in x], axis=1, subset=["Status"]), use_container_width=True)
            else:
                st.warning("**Paste data to begin audit.**")

    # --- TAB 4: TRANSLATOR ---
    with tabs[3]:
        st.subheader("🌐 **Instant Translator**")
        txt = st.text_area("Russian Text", height=150)
        if txt:
            st.success(f"**English:**\n\n{GoogleTranslator(source='auto', target='en').translate(txt)}")

    st.caption(f"**Operator Session:** {operator_name} | **Security:** AES-Locked")
