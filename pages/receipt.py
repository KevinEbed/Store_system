import streamlit as st
import pandas as pd
import io
import zipfile
from datetime import datetime
from database import get_connection

st.set_page_config(page_title="🧾 Receipts", layout="wide")
st.title("🧾 Receipts / Orders")

# Utility to pick available Excel engine
def available_excel_engine():
    try:
        import xlsxwriter  # noqa: F401
        return "xlsxwriter"
    except ImportError:
        try:
            import openpyxl  # noqa: F401
            return "openpyxl"
        except ImportError:
            return None

def make_excel_bytes(dfs: dict):
    engine = available_excel_engine()
    if engine is None:
        return None
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine=engine) as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        try:
            writer.save()
        except Exception:
            pass
    buf.seek(0)
    return buf

def make_zip_bytes(files: dict):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for fname, content in files.items():
            z.writestr(fname, content)
    buf.seek(0)
    return buf

# Load data
conn = get_connection()
orders_df = pd.read_sql_query("SELECT * FROM orders ORDER BY id DESC", conn)
order_items_df = pd.read_sql_query("SELECT * FROM order_items ORDER BY order_id DESC", conn)
products_df = pd.read_sql_query("SELECT * FROM products ORDER BY id", conn)

# Normalize stored total column
if not orders_df.empty and "total" in orders_df.columns:
    orders_df["total"] = pd.to_numeric(orders_df["total"], errors="coerce").fillna(0.0)

st.markdown("## All Orders")
st.dataframe(orders_df, use_container_width=True)

st.markdown("## Retake / Inspect an Order")
if orders_df.empty:
    st.info("No orders have been placed yet.")
else:
    selected_order_id = st.selectbox("Select order to inspect or retake", orders_df["id"].tolist())
    if selected_order_id is not None:
        # Extract order row and ensure total is correct (fallback from items if needed)
        order_row = orders_df[orders_df["id"] == selected_order_id].iloc[0].copy()
        try:
            total_val = float(order_row["total"])
        except (ValueError, TypeError):
            total_val = 0.0

        # Fallback: compute from order_items if stored total is zero
        items_subset = order_items_df[order_items_df["order_id"] == selected_order_id].copy()
        if total_val == 0.0 and not items_subset.empty:
            items_subset["price"] = pd.to_numeric(items_subset["price"], errors="coerce").fillna(0.0)
            items_subset["quantity"] = pd.to_numeric(items_subset["quantity"], errors="coerce").fillna(0).astype(int)
            total_val = (items_subset["price"] * items_subset["quantity"]).sum()

        order_row["total"] = float(total_val)

        st.markdown("### Order Summary")
        cols = st.columns(3)
        cols[0].markdown(f"**Order ID:** {order_row['id']}")
        cols[1].markdown(f"**Timestamp:** {order_row['timestamp']}")
        cols[2].markdown(f"**Total:** {order_row['total']:.2f} EGP")

        # Prepare items table
        items_df = order_items_df[order_items_df["order_id"] == selected_order_id].copy()
        if not items_df.empty:
            items_df = items_df[["product_id", "name", "price", "quantity"]].rename(columns={"product_id": "id"})
            items_df["price"] = pd.to_numeric(items_df["price"], errors="coerce").fillna(0.0)
            items_df["quantity"] = pd.to_numeric(items_df["quantity"], errors="coerce").fillna(0).astype(int)
            items_df["line_total"] = items_df["price"] * items_df["quantity"]
            st.markdown("### Items in Order")
            st.dataframe(items_df, use_container_width=True)
        else:
            st.warning("No items found for this order (unexpected).")

        # Retake into cart
        if st.button("🔁 Load this order into cart"):
            if "cart" not in st.session_state:
                st.session_state.cart = {}
            new_cart = {}
            if not items_df.empty:
                for _, row in items_df.iterrows():
                    new_cart[int(row["id"])] = {
                        "id": int(row["id"]),
                        "name": row["name"],
                        "price": row["price"],
                        "quantity": int(row["quantity"])
                    }
                st.session_state.cart = new_cart
                st.success(f"Order {selected_order_id} loaded into cart. Switch to the POS page to checkout.")
            else:
                st.error("Cannot load empty order into cart.")

        # Build receipt header and items for export
        def build_receipt_header(order):
            return pd.DataFrame({
                "Field": ["Order ID", "Timestamp", "Total"],
                "Value": [order["id"], order["timestamp"], f"{order['total']:.2f} EGP"]
            })

        receipt_header_df = build_receipt_header(order_row)
        receipt_items_df = pd.DataFrame()
        if not items_df.empty:
            receipt_items_df = items_df.rename(columns={
                "id": "Product ID",
                "name": "Name",
                "price": "Price",
                "quantity": "Quantity",
                "line_total": "Line Total"
            })[["Product ID", "Name", "Price", "Quantity", "Line Total"]]

        # Export single order
        st.markdown("#### 📥 Export this order")
        order_summary_df = pd.DataFrame([order_row])
        single_order_dfs = {
            "OrderSummary": order_summary_df,
            "OrderItems": items_df if not items_df.empty else pd.DataFrame()
        }

        engine = available_excel_engine()
        if engine:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine=engine) as writer:
                # Receipt sheet: header then items
                receipt_sheet = "Receipt"
                receipt_header_df.to_excel(writer, index=False, sheet_name=receipt_sheet, startrow=0)
                if not receipt_items_df.empty:
                    receipt_items_df.to_excel(writer, index=False, sheet_name=receipt_sheet, startrow=len(receipt_header_df) + 2)
                # Raw data sheets
                order_summary_df.to_excel(writer, index=False, sheet_name="OrderSummary")
                if not items_df.empty:
                    items_df.to_excel(writer, index=False, sheet_name="OrderItems")
                try:
                    writer.save()
                except Exception:
                    pass
            buf.seek(0)
            st.download_button(
                label=f"Download Order {selected_order_id} Receipt (.xlsx)",
                data=buf,
                file_name=f"receipt_order_{selected_order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            # Fallback ZIP of CSVs: include receipt header + items + raw
            files = {
                f"receipt_header_order_{selected_order_id}.csv": receipt_header_df.to_csv(index=False).encode(),
                f"receipt_items_order_{selected_order_id}.csv": receipt_items_df.to_csv(index=False).encode() if not receipt_items_df.empty else b"",
                f"order_summary_{selected_order_id}.csv": order_summary_df.to_csv(index=False).encode(),
                f"order_items_{selected_order_id}.csv": items_df.to_csv(index=False).encode() if not items_df.empty else b"",
            }
            zip_buf = make_zip_bytes(files)
            st.warning("Excel engine not available; providing ZIP of CSVs instead.")
            st.download_button(
                label=f"Download Order {selected_order_id} Receipt (ZIP)",
                data=zip_buf,
                file_name=f"receipt_order_{selected_order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip"
            )

# Full export
st.markdown("---")
st.markdown("## 📦 Full Export (All Orders + Items + Inventory)")
all_dfs = {"Orders": orders_df, "OrderItems": order_items_df, "Inventory": products_df}
excel_full = make_excel_bytes(all_dfs)
if excel_full:
    st.download_button(
        label="📥 Download Everything (Excel)",
        data=excel_full,
        file_name=f"full_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    files = {
        "orders.csv": orders_df.to_csv(index=False).encode(),
        "order_items.csv": order_items_df.to_csv(index=False).encode(),
        "inventory.csv": products_df.to_csv(index=False).encode(),
    }
    zip_full = make_zip_bytes(files)
    st.warning("Excel export unavailable; providing ZIP of CSVs instead.")
    st.download_button(
        label="📥 Download Everything (ZIP)",
        data=zip_full,
        file_name=f"full_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        mime="application/zip"
    )

conn.close()
