import streamlit as st
import pandas as pd
import io
from datetime import datetime
from database import get_connection

st.set_page_config(page_title="🧾 Receipts", layout="wide")
st.title("🧾 Receipts / Orders")

# Load orders and items
conn = get_connection()
orders_df = pd.read_sql_query("SELECT * FROM orders ORDER BY id DESC", conn)
order_items_df = pd.read_sql_query("SELECT * FROM order_items ORDER BY order_id DESC", conn)
products_df = pd.read_sql_query("SELECT * FROM products ORDER BY id", conn)

# --- Overview & selection ---
st.markdown("## All Orders")
st.dataframe(orders_df, use_container_width=True)

st.markdown("## Retake / Inspect an Order")
if orders_df.empty:
    st.info("No orders have been placed yet.")
else:
    selected_order_id = st.selectbox("Select order to inspect or retake", orders_df["id"].tolist())
    if selected_order_id is not None:
        # Show summary
        order_row = orders_df[orders_df["id"] == selected_order_id].iloc[0]
        st.markdown("### Order Summary")
        cols = st.columns(3)
        cols[0].markdown(f"**Order ID:** {order_row['id']}")
        cols[1].markdown(f"**Timestamp:** {order_row['timestamp']}")
        cols[2].markdown(f"**Total:** {order_row['total']} EGP")

        # Items
        items_df = order_items_df[order_items_df["order_id"] == selected_order_id].copy()
        if not items_df.empty:
            items_df = items_df[["product_id", "name", "price", "quantity"]]
            items_df = items_df.rename(columns={"product_id": "id"})
            items_df["total"] = items_df["price"] * items_df["quantity"]
            st.markdown("### Items in Order")
            st.dataframe(items_df, use_container_width=True)
        else:
            st.warning("No items found for this order (unexpected).")

        # Retake: load into cart
        if st.button("🔁 Load this order into cart"):
            # Reconstruct cart in session state
            new_cart = {}
            for _, row in items_df.iterrows():
                new_cart[int(row["id"])] = {
                    "id": int(row["id"]),
                    "name": row["name"],
                    "price": row["price"],
                    "quantity": int(row["quantity"])
                }
            st.session_state.cart = new_cart
            st.success(f"Order {selected_order_id} loaded into cart. Switch to the POS page to checkout.")

        # Download this order as a standalone Excel
        st.markdown("#### 📥 Export this order")
        towrite = io.BytesIO()
        with pd.ExcelWriter(towrite, engine="xlsxwriter") as writer:
            pd.DataFrame([order_row]).to_excel(writer, index=False, sheet_name="OrderSummary")
            items_df.to_excel(writer, index=False, sheet_name="OrderItems")
            writer.save()
        towrite.seek(0)
        st.download_button(
            label=f"Download Order {selected_order_id} Excel",
            data=towrite,
            file_name=f"order_{selected_order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- Full export ---
st.markdown("---")
st.markdown("## 📦 Full Export (All Orders + Items + Inventory)")
full_export_buf = io.BytesIO()
with pd.ExcelWriter(full_export_buf, engine="xlsxwriter") as writer:
    orders_df.to_excel(writer, index=False, sheet_name="Orders")
    order_items_df.to_excel(writer, index=False, sheet_name="OrderItems")
    products_df.to_excel(writer, index=False, sheet_name="Inventory")
    writer.save()
full_export_buf.seek(0)
st.download_button(
    label="📥 Download Everything (Excel)",
    data=full_export_buf,
    file_name=f"full_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

conn.close()
