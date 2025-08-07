import streamlit as st
import pandas as pd
import io
import zipfile
from datetime import datetime
from database import get_connection
import pytz  # For timezone support

st.set_page_config(page_title="Receipts", layout="wide")
st.title("Receipts / Orders")

def available_excel_engine():
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
        for name, df in dfs.items():
            if name == "Orders":
                # Select id, date, time, total, and camper_name columns
                df = df[["id", "date", "time", "total", "camper_name"]].copy()
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                df["time"] = df["time"]  # Already in EEST format
                df["total"] = df["total"].round(2)  # Ensure total is formatted with 2 decimals
            elif name == "Combined Receipts":
                # Custom formatting for Combined Receipts
                df = df.copy()
            df.to_excel(writer, index=False, sheet_name=name[:31])
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
conn.close()

# Normalize and compute line totals
order_items_df["price"] = pd.to_numeric(order_items_df["price"], errors="coerce").fillna(0.0)
order_items_df["quantity"] = pd.to_numeric(order_items_df["quantity"], errors="coerce").fillna(0).astype(int)
order_items_df["line_total"] = order_items_df["price"] * order_items_df["quantity"]

# Recalculate order totals from items when needed
recalc = (
    order_items_df.groupby("order_id", as_index=False)["line_total"]
    .sum()
    .rename(columns={"order_id": "id", "line_total": "total_from_items"})
)
orders_df["total"] = pd.to_numeric(orders_df.get("total", 0), errors="coerce").fillna(0.0)
orders_df = orders_df.merge(recalc, on="id", how="left")
orders_df["total"] = orders_df["total_from_items"].where(
    orders_df["total_from_items"].notna() & (orders_df["total_from_items"] != 0),
    orders_df["total"]
)
orders_df.drop(columns=["total_from_items"], inplace=True)

# Parse timestamp with Egyptian time (EEST, UTC+3)
eest = pytz.timezone("Africa/Cairo")
orders_df["parsed_ts"] = pd.to_datetime(orders_df.get("timestamp", ""), utc=True).dt.tz_convert(eest) if "timestamp" in orders_df else pd.NaT
orders_df["date"] = orders_df["parsed_ts"].dt.date
orders_df["time"] = orders_df["parsed_ts"].dt.strftime("%H:%M:%S")

# Prepare Combined Receipts data
combined_receipts_data = []
for order_id in orders_df["id"].unique():
    order_row = orders_df[orders_df["id"] == order_id].iloc[0]
    combined_receipts_data.append(["Header", "Order ID", order_id])
    combined_receipts_data.append(["Header", "Timestamp", order_row["parsed_ts"].strftime("%Y-%m-%d %H:%M:%S")])
    combined_receipts_data.append(["Header", "Total", f"{order_row['total']:.2f} EGP"])
    combined_receipts_data.append(["Header", "Camper Name", order_row.get("camper_name", "N/A")])  # Add camper name
    combined_receipts_data.append(["Items", "", ""])  # Separator for items
    items = order_items_df[order_items_df["order_id"] == order_id]
    for _, item in items.iterrows():
        combined_receipts_data.append(["Items", item["name"], f"{item['quantity']} x {item['price']:.2f} = {item['line_total']:.2f}"])

# Create DataFrame for Combined Receipts
combined_receipts_df = pd.DataFrame(combined_receipts_data, columns=["Section", "Field", "Value"])

# Prepare Camper Summary data with items
camper_summary_data = []
camper_groups = orders_df.groupby("camper_name")
for camper_name, group in camper_groups:
    total_paid = group["total"].sum().round(2)
    order_ids = ", ".join(group["id"].astype(str))
    items_list = []
    for order_id in group["id"]:
        order_items = order_items_df[order_items_df["order_id"] == order_id]
        for _, item in order_items.iterrows():
            items_list.append(f"{item['name']} ({item['quantity']} x {item['price']:.2f} = {item['line_total']:.2f})")
    items_str = "; ".join(items_list) if items_list else "No items"
    camper_summary_data.append([camper_name, total_paid, order_ids, items_str])

camper_summary_df = pd.DataFrame(camper_summary_data, columns=["Camper Name", "Total Paid (EGP)", "Order IDs", "Items Ordered"])

# Daily totals
daily_totals_df = (
    orders_df.dropna(subset=["date"])
    .groupby("date", as_index=False)["total"]
    .sum()
    .rename(columns={"total": "daily_total"})
)
daily_totals_df["daily_total"] = daily_totals_df["daily_total"].round(2)

# Display
st.subheader("All Orders")
st.dataframe(orders_df[["id", "date", "time", "total", "camper_name"]], use_container_width=True)

st.subheader("Daily Sales Summary")
if not daily_totals_df.empty:
    st.dataframe(daily_totals_df, use_container_width=True)
    st.markdown(f"**Total across all days:** {daily_totals_df['daily_total'].sum():.2f} EGP")
else:
    st.info("No sales data.")

st.subheader("Inspect Order")
if not orders_df.empty:
    selected = st.selectbox("Order ID", orders_df["id"].tolist())
    order_row = orders_df[orders_df["id"] == selected].iloc[0]
    st.markdown(f"**Order {selected}** — Total: {order_row['total']:.2f} EGP — {order_row['parsed_ts'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
    st.markdown(f"**Camper Name:** {order_row.get('camper_name', 'N/A')}")
    items_df = order_items_df[order_items_df["order_id"] == selected].copy()
    if not items_df.empty:
        items_df["line_total"] = items_df["price"] * items_df["quantity"]
        st.dataframe(
            items_df[["product_id", "name", "size", "price", "quantity", "line_total"]],
            use_container_width=True
        )
        if st.button("Load into Cart"):
            if "cart" not in st.session_state:
                st.session_state.cart = {}
            new_cart = {}
            for _, r in items_df.iterrows():
                item = {
                    "id": int(r["product_id"]),
                    "name": r["name"],
                    "size": r.get("size", ""),
                    "price": r["price"],
                    "quantity": int(r["quantity"])
                }
                if item["id"] in new_cart:
                    new_cart[item["id"]]["quantity"] += item["quantity"]
                else:
                    new_cart[item["id"]] = item
            st.session_state.cart = new_cart
            st.success("Loaded order into cart. Go to POS page to checkout.")
    else:
        st.warning("No items for this order.")

# Full export
st.markdown("---")
st.subheader("Full Export")
combined = {
    "Orders": orders_df,
    "OrderItems": order_items_df,
    "Inventory": products_df,
    "DailyTotals": daily_totals_df,
    "Combined Receipts": combined_receipts_df,
    "Camper Summary": camper_summary_df  # Updated with items
}
excel = make_excel_bytes(combined)
if excel:
    st.download_button(
        "Download Full Export (.xlsx)",
        data=excel,
        file_name=f"full_export_{datetime.now(pytz.timezone('Africa/Cairo')).strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    files = {
        "orders.csv": orders_df.to_csv(index=False).encode(),
        "order_items.csv": order_items_df.to_csv(index=False).encode(),
        "inventory.csv": products_df.to_csv(index=False).encode(),
        "daily_totals.csv": daily_totals_df.to_csv(index=False).encode(),
    }
    zipb = make_zip_bytes(files)
    st.download_button(
        "Download Full Export (ZIP)",
        data=zipb,
        file_name=f"full_export_{datetime.now(pytz.timezone('Africa/Cairo')).strftime('%Y%m%d_%H%M%S')}.zip",
        mime="application/zip"
    )
