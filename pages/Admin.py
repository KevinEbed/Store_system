import streamlit as st
import pandas as pd
import io
from database import get_connection, init_db

st.set_page_config(page_title="Admin Upload", layout="wide")
init_db()

def upload_inventory():
    st.header("Upload Inventory")
    uploaded_file = st.file_uploader("Excel or CSV", type=["xlsx", "csv"])
    conn = get_connection()
    existing_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    if uploaded_file:
        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.dataframe(df)

        overwrite = st.checkbox("Overwrite existing products?", value=False, disabled=(existing_count == 0))
        if st.button("Upload to Database"):
            c = conn.cursor()
            if existing_count > 0 and not overwrite:
                st.warning("Products exist; enable overwrite to replace.")
            else:
                if overwrite:
                    c.execute("DELETE FROM products")
                for _, row in df.iterrows():
                    c.execute("""
                        INSERT INTO products (id, name, category, size, price, quantity)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        int(row["id"]),
                        row["name"],
                        row.get("category", ""),
                        row.get("size", ""),
                        int(row["price"]),
                        int(row["quantity"])
                    ))
                conn.commit()
                st.success("Inventory uploaded.")
    conn.close()

upload_inventory()
