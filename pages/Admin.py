import streamlit as st
import pandas as pd
from database import get_connection, init_db

st.set_page_config(page_title="Admin Upload", layout="wide")
init_db()

def upload_inventory():
    st.header("Upload Inventory")
    uploaded_file = st.file_uploader("Excel or CSV", type=["xlsx", "csv"])
    conn = get_connection()
    existing_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    if existing_count > 0:
        if st.button("Clear and Replace Data"):
            c = conn.cursor()
            c.execute("DELETE FROM products")
            # Reset auto-increment if using SQLite sequence
            c.execute("DELETE FROM sqlite_sequence WHERE name='products'")
            conn.commit()
            st.success("All existing data has been cleared. Please upload new data.")
            st.experimental_rerun()

    if uploaded_file:
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            # Validate required columns
            required_columns = {"name", "price", "quantity"}
            if not all(col in df.columns for col in required_columns):
                st.error("Uploaded file must contain columns: name, price, quantity.")
                return

            # Ensure id column exists or generate unique ids
            if "id" not in df.columns:
                df["id"] = range(1, len(df) + 1)  # Auto-generate ids if missing
            else:
                df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
                if df["id"].duplicated().any():
                    st.warning("Duplicate ids detected. Generating unique ids based on name and size.")
                    # Create unique ids by combining name and size (if size exists)
                    df["temp_id"] = df.apply(lambda row: f"{row['name']}_{row.get('size', '')}".replace(" ", "_"), axis=1)
                    df["id"] = pd.factorize(df["temp_id"])[0] + 1  # Generate unique numeric ids

            # Convert columns to appropriate types and handle NaN
            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0).astype(int)
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
            df["category"] = df["category"].fillna("")
            df["size"] = df["size"].fillna("")

            st.dataframe(df)

            overwrite = st.checkbox("Overwrite existing products?", value=False, disabled=(existing_count == 0))
            if st.button("Upload to Database"):
                c = conn.cursor()
                if existing_count > 0 and not overwrite:
                    st.warning("Products exist; enable overwrite to replace.")
                else:
                    if overwrite or existing_count == 0:
                        c.execute("DELETE FROM products")
                        # Reset auto-increment if using SQLite sequence
                        c.execute("DELETE FROM sqlite_sequence WHERE name='products'")
                    for _, row in df.iterrows():
                        c.execute("""
                            INSERT INTO products (id, name, category, size, price, quantity)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            row["id"],
                            row["name"],
                            row["category"],
                            row["size"],
                            row["price"],
                            row["quantity"]
                        ))
                    conn.commit()
                    st.success("Inventory uploaded successfully.")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
        finally:
            conn.close()
    else:
        conn.close()

upload_inventory()
