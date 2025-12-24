import streamlit as st
import pandas as pd
from cre_extractor import extract_and_update_db

DB_PATH = "txn db_Dec25.xlsx"

st.set_page_config(page_title="CRE Transaction Extractor", layout="wide")

st.title("🏢 Commercial Real Estate Transaction Extractor")

st.markdown("""
Upload a news article (TXT file).  
The system will extract transaction details, append them to the database,  
and display the updated results.
""")

uploaded_file = st.file_uploader(
    "Upload news article (.txt)",
    type=["txt"]
)

if uploaded_file:
    article_text = uploaded_file.read().decode("utf-8")

    with st.expander("📄 View uploaded article"):
        st.text(article_text)

    if st.button("🚀 Extract & Update Database"):
        with st.spinner("Processing article with AI..."):
            success = extract_and_update_db(article_text, DB_PATH)

        if success:
            st.success("Database updated successfully!")

            df = pd.read_excel(DB_PATH)

            st.subheader("📊 Updated Transaction Database")
            st.dataframe(df, use_container_width=True)

        else:
            st.error("Extraction failed. Check logs.")
