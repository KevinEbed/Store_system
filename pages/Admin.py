import streamlit as st
import pandas as pd
from database import get_connection

st.set_page_config(page_title="📤 Admin Upload")

st.title("📤 Upload Product Inventory")

uploaded_file = st.file_uploader("Upload Excel or CSV", type=["xlsx", "csv"])

conn = get_connection()
existing_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.dataframe(df)

    overwrite = st.checkbox("⚠️ Overwrite existing products?", value=False, disabled=(existing_count == 0))

    if st.button("🚀 Upload to Database"):
        c = conn.cursor()
        if existing_count > 0 and not overwrite:
            st.warning("❌ Products exist. Enable overwrite to replace.")
        else:
            if overwrite:
                c.execute("DELETE FROM products")
                conn.commit()

            for _, row in df.iterrows():
                c.execute("""
                    INSERT INTO products (id, name, category, size, price, quantity)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (row["id"], row["name"], row["category"], row["size"], row["price"], row["quantity"]))
            conn.commit()
            st.success("✅ Uploaded successfully.")
    conn.close()
