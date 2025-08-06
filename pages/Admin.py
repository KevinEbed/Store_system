import streamlit as st
import pandas as pd
import io
from database import get_connection, init_db

st.set_page_config(page_title="Admin Dashboard", layout="wide")
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
                        ON CONFLICT(id) DO UPDATE SET
                            name=excluded.name,
                            category=excluded.category,
                            size=excluded.size,
                            price=excluded.price,
                            quantity=excluded.quantity
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

def dashboard():
    st.header("Admin Dashboard")
    if st.button("Refresh"):
        st.experimental_rerun()

    conn = get_connection()
    orders_df = pd.read_sql_query("SELECT * FROM orders ORDER BY id DESC", conn)
    order_items_df = pd.read_sql_query("SELECT * FROM order_items ORDER BY order_id DESC", conn)
    products_df = pd.read_sql_query("SELECT * FROM products ORDER BY id", conn)

    st.subheader("Orders")
    st.dataframe(orders_df)

    st.subheader("Order Items")
    st.dataframe(order_items_df)

    st.subheader("Inventory")
    st.dataframe(products_df)

    st.markdown("Download Inventory")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        products_df.to_excel(writer, index=False, sheet_name="Inventory")
    buf.seek(0)
    st.download_button(
        "Download Inventory Excel",
        data=buf,
        file_name="inventory.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    conn.close()

page = st.sidebar.selectbox("Admin", ["Dashboard", "Upload"])
if page == "Dashboard":
    dashboard()
else:
    upload_inventory()
