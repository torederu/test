import streamlit as st
import pandas as pd
import io
import time
from utils.scraping_utils import scrape_thorne_gut_report
from supabase_utils import get_user_supabase

def thorne_tab(username):
    user_supabase = get_user_supabase()
    # === Try to restore saved CSV (stateless ghost-block logic)
    if not st.session_state.get("thorne_csv_ready"):
        try:
            bucket = user_supabase.storage.from_("data")
            thorne_filename = f"{username}/thorne.csv"
            res = bucket.download(thorne_filename)
            files = bucket.list(path=f"{username}/")
            in_list = any(f["name"] == "thorne.csv" for f in files)
            if res and len(res) > 0 and not in_list:
                st.session_state.thorne_csv_ready = False
            elif res and len(res) > 0:
                thorne_df = pd.read_csv(io.BytesIO(res))
                st.session_state.thorne_csv = res
                st.session_state.thorne_df = thorne_df
                st.session_state.thorne_csv_ready = True
            else:
                st.session_state.thorne_csv_ready = False
        except Exception:
            st.session_state.thorne_csv_ready = False
    
    st.markdown("<h1>Thorne Gut Health</h1>", unsafe_allow_html=True)
    
    if st.session_state.get("deleting_thorne_in_progress", False):
        with st.spinner("Deleting file from database..."):
            st.session_state.pop("thorne_csv_ready", None)
            st.session_state.pop("thorne_csv", None)
            st.session_state.pop("thorne_df", None)
            st.session_state.pop("thorne_csv_filename", None)
            st.session_state.pop("thorne_supabase_uploaded", None)
            st.session_state.pop("thorne_email", None)
            st.session_state.pop("thorne_password", None)
            try:
                bucket = user_supabase.storage.from_("data")
                bucket.remove([f"{username}/thorne.csv"])
                max_attempts = 20
                file_still_exists = True
                for attempt in range(max_attempts):
                    time.sleep(3)
                    files = bucket.list(path=f"{username}/")
                    file_still_exists = any(f["name"] == "thorne.csv" for f in files)
                    if not file_still_exists:
                        break
                if not file_still_exists:
                    st.success("Resetting...")
                    time.sleep(1.5)
                    st.session_state.skip_restore = True
                    st.session_state.deletion_successful = True
                    st.session_state.just_deleted = True
                    st.session_state.pop("deleting_thorne_in_progress", None)
                    st.rerun()
                else:
                    st.error("File deletion timed out after 60 seconds. Please try again or check your connection.")
            except Exception as e:
                st.error(f"Something went wrong while deleting your file: {e}")
    elif st.session_state.get("thorne_csv_ready") and "thorne_df" in st.session_state:
        st.markdown("Double-click any cell to reveal its full contents.")
        st.dataframe(st.session_state.thorne_df)
        st.success("Import successful!")
        time.sleep(1)
        if st.button("Start Over", key="reset_thorne"):
            st.session_state.deleting_thorne_in_progress = True
            st.rerun()
    else:
        st.markdown("""
    <div style='font-size:17.5px; line-height:1.6'>
    Please enter your Thorne credentials to connect and download your data.
    </div>""", unsafe_allow_html=True)
        st.markdown("""
    <div style='font-size:17.5px; line-height:1.6; margin-top:0.5rem; margin-bottom:1.5rem;'>
    <strong>Your Information Stays Private:</strong> We do not store your credentials. They are used once to connect to Thorne to download your data, and then are immediately erased from memory.
    </div>""", unsafe_allow_html=True)
        # If not loaded, show login form
        with st.form("thorne_login_form"):
            user_email = st.text_input("Thorne Email", key="thorne_email")
            user_pass = st.text_input("Thorne Password", type="password", key="thorne_password")
            submitted = st.form_submit_button("Connect & Import Data")
        if submitted:
            if not user_email or not user_pass:
                st.error("Please enter email and password.")
                st.stop()
            
            st.session_state.pop("skip_restore", None)
            with st.spinner("Importing Thorne Data"):
                status = st.empty()
                try:
                    thorne_df = scrape_thorne_gut_report(user_email, user_pass, status)
                    status.markdown(
                        '<div style="margin-left:2.3em; font-size:1rem; font-weight:400; line-height:1.2; margin-top:-0.6em; margin-bottom:0.1em;">⤷ Deleting Thorne credentials from memory</div>',
                        unsafe_allow_html=True
                    )
                    del user_email
                    del user_pass
                    st.session_state.pop("thorne_email", None)
                    st.session_state.pop("thorne_password", None)
                    thorne_csv_bytes = thorne_df.to_csv(index=False).encode()
                    st.session_state.thorne_csv = thorne_csv_bytes
                    st.session_state.thorne_df = thorne_df
                    st.session_state.thorne_csv_filename = f"{username}_thorne.csv"
                    st.session_state.thorne_csv_file = thorne_csv_bytes
                    # Upload to Supabase
                    try:
                        bucket = user_supabase.storage.from_("data")
                        bucket.remove([f"{username}/thorne.csv"])
                    except Exception:
                        pass
                    response = bucket.upload(
                        path=f"{username}/thorne.csv",
                        file=thorne_csv_bytes,
                        file_options={"content-type": "text/csv"}
                    )
                    res_data = response.__dict__
                    if "error" in res_data and res_data["error"]:
                        st.error("Upload failed.")
                    else:
                        st.session_state.thorne_supabase_uploaded = True
                    status.markdown(
                        '<div style="margin-left:2.3em; font-size:1rem; font-weight:400; line-height:1.2; margin-top:-0.6em; margin-bottom:0.1em;">⤷ Import successful!</div>',
                        unsafe_allow_html=True
                    )
                    st.session_state.to_initialize_thorne_csv = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Import failed: {type(e).__name__} — {e}")
            status.empty() 