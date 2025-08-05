import streamlit as st
import pandas as pd
import io
from database import get_connection

st.set_page_config(page_title="🛠️ Admin Dashboard")

def upload_inventory():
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

def admin_dashboard():
    st.title("🛠️ Admin Dashboard")

    if st.button("🔄 Refresh Data"):
        st.experimental_rerun()

    conn = get_connection()
    orders_df = pd.read_sql_query("SELECT * FROM orders ORDER BY id DESC", conn)
    order_items_df = pd.read_sql_query("SELECT * FROM order_items ORDER BY order_id DESC", conn)
    products_df = pd.read_sql_query("SELECT * FROM products ORDER BY id", conn)

    st.markdown("### 🧾 All Orders")
    st.dataframe(orders_df)

    st.markdown("### 📦 Order Items (Latest first)")
    st.dataframe(order_items_df)

    st.markdown("### 📥 Download Current Inventory")
    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
        products_df.to_excel(writer, index=False, sheet_name="Inventory")
        writer.save()
    towrite.seek(0)

    st.download_button(
        label="📥 Download Inventory Excel",
        data=towrite,
        file_name="inventory.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    conn.close()

page = st.sidebar.radio("Select Admin Page", ["Dashboard", "Upload Inventory"])

if page == "Dashboard":
    admin_dashboard()
elif page == "Upload Inventory":
    upload_inventory()
