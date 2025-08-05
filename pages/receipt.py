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

# --- Data Loading --- #
conn = get_connection()
orders_df = pd.read_sql_query("SELECT * FROM orders ORDER BY id DESC", conn)
order_items_df = pd.read_sql_query("SELECT * FROM order_items ORDER BY order_id DESC", conn)
products_df = pd.read_sql_query("SELECT * FROM products ORDER BY id", conn)

# --- Recalculate / Normalize Totals --- #
order_items_df["price"] = pd.to_numeric(order_items_df["price"], errors="coerce").fillna(0.0)
order_items_df["quantity"] = pd.to_numeric(order_items_df["quantity"], errors="coerce").fillna(0).astype(int)
order_items_df["line_total"] = order_items_df["price"] * order_items_df["quantity"]

# Recalculate total per order from items
recalc_totals = (
    order_items_df.groupby("order_id", as_index=False)["line_total"]
    .sum()
    .rename(columns={"order_id": "id", "line_total": "total_from_items"})
)

# Ensure orders_df has numeric total (fallback)
orders_df["total"] = pd.to_numeric(orders_df.get("total", 0), errors="coerce").fillna(0.0)

# Merge and prefer the recalculated total if present and nonzero
orders_df = orders_df.merge(recalc_totals, on="id", how="left")
orders_df["total"] = orders_df["total_from_items"].where(
    orders_df["total_from_items"].notna() & (orders_df["total_from_items"] != 0),
    orders_df["total"]
)
orders_df.drop(columns=["total_from_items"], inplace=True)

# --- Parse timestamp to date for daily aggregation --- #
def safe_parse_datetime(s):
    try:
        return pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    except Exception as e:
        st.warning(f"Failed to parse timestamp '{s}': {e}")
        return pd.NaT

if "timestamp" not in orders_df.columns:
    st.error("Orders table is missing the 'timestamp' column.")
    orders_df["parsed_ts"] = pd.NaT
else:
    orders_df["parsed_ts"] = orders_df["timestamp"].apply(safe_parse_datetime)

# Always create date column (can be NaT)
orders_df["date"] = orders_df["parsed_ts"].dt.date

# Feedback on parsing
if orders_df["parsed_ts"].isna().all():
    st.error("Timestamp conversion failed for all rows. Check 'timestamp' column values.")
    if "timestamp" in orders_df.columns:
        st.write("Sample problematic timestamp values:", orders_df["timestamp"].unique()[:10])
else:
    bad_ts = orders_df[orders_df["parsed_ts"].isna()]
    if not bad_ts.empty:
        st.warning(f"{len(bad_ts)} row(s) have unparsable timestamps and will be excluded from daily totals.")
        st.write("Example invalid timestamps:", bad_ts["timestamp"].unique()[:10])

# --- Daily totals --- #
daily_totals_df = (
    orders_df.dropna(subset=["date"])
    .groupby("date", as_index=False)["total"]
    .sum()
    .rename(columns={"total": "daily_total"})
)
daily_totals_df["daily_total"] = daily_totals_df["daily_total"].round(2)

# --- Display --- #
st.markdown("## All Orders")
st.dataframe(orders_df.drop(columns=["parsed_ts"], errors="ignore"), use_container_width=True)

st.markdown("## Daily Sales Summary")
if daily_totals_df.empty:
    st.info("No sales data to aggregate by day.")
else:
    st.dataframe(daily_totals_df, use_container_width=True)
    total_overall = daily_totals_df["daily_total"].sum()
    st.markdown(f"**Total across all days:** {total_overall:.2f} EGP")

st.markdown("## Retake / Inspect an Order")
if orders_df.empty:
    st.info("No orders have been placed yet.")
else:
    selected_order_id = st.selectbox("Select order to inspect or retake", orders_df["id"].tolist())
    if selected_order_id is not None:
        # Extract order row
        order_row = orders_df[orders_df["id"] == selected_order_id].iloc[0].copy()
        try:
            order_row["total"] = float(order_row["total"])
        except (ValueError, TypeError):
            order_row["total"] = 0.0

        st.markdown("### Order Summary")
        cols = st.columns(3)
        cols[0].markdown(f"**Order ID:** {order_row['id']}")
        cols[1].markdown(f"**Timestamp:** {order_row.get('timestamp', 'N/A')}")
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

        # Build receipt header and detailed items
        def build_receipt_header(order):
            return pd.DataFrame({
                "Field": ["Order ID", "Timestamp", "Total"],
                "Value": [order["id"], order.get("timestamp", ""), f"{order['total']:.2f} EGP"]
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

        # Single order export
        st.markdown("#### 📥 Export this order")
        order_summary_df = pd.DataFrame([order_row])
        engine = available_excel_engine()
        if engine:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine=engine) as writer:
                receipt_sheet = "Receipt"
                receipt_header_df.to_excel(writer, index=False, sheet_name=receipt_sheet, startrow=0)
                if not receipt_items_df.empty:
                    receipt_items_df.to_excel(writer, index=False, sheet_name=receipt_sheet, startrow=len(receipt_header_df) + 2)
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

# --- Full export with combined detailed receipts and daily totals --- #
st.markdown("---")
st.markdown("## 📦 Full Export (All Orders + Items + Inventory)")

def build_combined_receipts(orders: pd.DataFrame, items: pd.DataFrame):
    blocks = []
    for _, order in orders.sort_values("id", ascending=False).iterrows():
        order_copy = order.copy()
        try:
            total_val = float(order_copy["total"])
        except (ValueError, TypeError):
            total_val = 0.0
        items_subset = items[items["order_id"] == order_copy["id"]].copy()
        if total_val == 0.0 and not items_subset.empty:
            items_subset["price"] = pd.to_numeric(items_subset["price"], errors="coerce").fillna(0.0)
            items_subset["quantity"] = pd.to_numeric(items_subset["quantity"], errors="coerce").fillna(0).astype(int)
            total_val = (items_subset["price"] * items_subset["quantity"]).sum()
        order_copy["total"] = float(total_val)

        header_df = pd.DataFrame({
            "Field": ["Order ID", "Timestamp", "Total"],
            "Value": [order_copy["id"], order_copy.get("timestamp", ""), f"{order_copy['total']:.2f} EGP"]
        })
        detail_df = items[items["order_id"] == order_copy["id"]].copy()
        if not detail_df.empty:
            detail_df = detail_df[["product_id", "name", "price", "quantity"]].rename(
                columns={"product_id": "Product ID", "name": "Name"}
            )
            detail_df["Price"] = pd.to_numeric(detail_df["price"], errors="coerce").fillna(0.0)
            detail_df["Quantity"] = pd.to_numeric(detail_df["quantity"], errors="coerce").fillna(0).astype(int)
            detail_df["Line Total"] = detail_df["Price"] * detail_df["Quantity"]
            detail_df = detail_df[["Product ID", "Name", "Price", "Quantity", "Line Total"]]
        else:
            detail_df = pd.DataFrame(columns=["Product ID", "Name", "Price", "Quantity", "Line Total"])

        blocks.append(("header", header_df))
        blocks.append(("items", detail_df))
        blocks.append(("sep", pd.DataFrame([{}])))

    combined_rows = []
    for typ, df_block in blocks:
        if typ == "header":
            combined_rows.append({"Section": "Header", "Field": "", "Value": ""})
            for _, r in df_block.iterrows():
                combined_rows.append({"Section": "", "Field": r["Field"], "Value": r["Value"]})
        elif typ == "items":
            combined_rows.append({"Section": "Items", "Field": "", "Value": ""})
            for _, r in df_block.iterrows():
                combined_rows.append({
                    "Section": "",
                    "Field": r["Name"],
                    "Value": f"{r['Quantity']} x {r['Price']} = {r['Line Total']:.2f}"
                })
        else:
            combined_rows.append({"Section": "", "Field": "", "Value": ""})

    combined_df = pd.DataFrame(combined_rows)
    return combined_df

combined_receipts_df = build_combined_receipts(orders_df, order_items_df)

# Assemble full export
all_dfs = {
    "CombinedReceipts": combined_receipts_df,
    "DailyTotals": daily_totals_df,
    "Orders": orders_df,
    "OrderItems": order_items_df,
    "Inventory": products_df
}

excel_full = make_excel_bytes(all_dfs)
if excel_full:
    st.download_button(
        label="📥 Download Everything (Excel with Detailed Receipts)",
        data=excel_full,
        file_name=f"full_export_detailed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    files = {
        "combined_receipts.csv": combined_receipts_df.to_csv(index=False).encode(),
        "daily_totals.csv": daily_totals_df.to_csv(index=False).encode(),
        "orders.csv": orders_df.to_csv(index=False).encode(),
        "order_items.csv": order_items_df.to_csv(index=False).encode(),
        "inventory.csv": products_df.to_csv(index=False).encode(),
    }
    zip_full = make_zip_bytes(files)
    st.warning("Excel engine unavailable; providing ZIP of CSVs instead.")
    st.download_button(
        label="📥 Download Everything (ZIP with Detailed Receipts)",
        data=zip_full,
        file_name=f"full_export_detailed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        mime="application/zip"
    )

conn.close()
