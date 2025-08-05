import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from database import init_db, get_products, save_order, get_connection

st.set_page_config(page_title="🛍️ POS System", layout="wide")
st.title("🛍️ Clothing Store – Point of Sale")

# ------------------ Session State Init ------------------ #
init_db()
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "checkout_in_progress" not in st.session_state:
    st.session_state.checkout_in_progress = False

def reload_products():
    # Explicit reload helper (called on demand or after checkout)
    return get_products()

# ------------------ Manual Refresh ------------------ #
if st.button("🔄 Refresh Products"):
    st.experimental_rerun()

# ------------------ Retake Previous Order UI (optional) ------------------ #
with st.expander("🕘 Retake Previous Order", expanded=False):
    col1, col2 = st.columns([3, 1])
    with col1:
        conn = get_connection()
        orders_df = pd.read_sql_query("SELECT * FROM orders ORDER BY id DESC LIMIT 50", conn)
        order_ids = orders_df["id"].tolist()
        if order_ids:
            selected_order = st.selectbox("Select Order to Retake", order_ids)
        else:
            selected_order = None
            st.info("No previous orders found.")

        if selected_order is not None:
            order_row = orders_df[orders_df["id"] == selected_order].iloc[0]
            st.markdown(f"**Order ID:** {order_row['id']}")
            st.markdown(f"**Timestamp:** {order_row['timestamp']}")
            st.markdown(f"**Total:** {order_row['total']} EGP")

            items_df = pd.read_sql_query(
                "SELECT product_id AS id, name, price, quantity FROM order_items WHERE order_id = ?",
                conn,
                params=(selected_order,)
            )
            items_df["total"] = items_df["price"] * items_df["quantity"]
            st.markdown("#### Items in that order")
            st.dataframe(items_df, use_container_width=True)

            if st.button("🔁 Load this order into cart"):
                new_cart = {}
                for _, row in items_df.iterrows():
                    new_cart[int(row["id"])] = {
                        "id": int(row["id"]),
                        "name": row["name"],
                        "price": row["price"],
                        "quantity": int(row["quantity"])
                    }
                st.session_state.cart = new_cart
                st.success(f"Loaded order {selected_order} into cart.")
                st.experimental_rerun()
    with col2:
        if st.button("🔄 Refresh Orders/Retake UI"):
            st.experimental_rerun()
    conn.close()

# ------------------ Load Products ------------------ #
products = reload_products()

# ------------------ Product Grid ------------------ #
st.markdown("## 🛍️ Products")
cols = st.columns(4)
for i, item in enumerate(products):
    with cols[i % 4]:
        st.markdown(f"### {item['name']}")

        image_path = f"data/images/{item['id']}.jpg"
        if os.path.exists(image_path):
            st.image(image_path, use_container_width=True)
        else:
            placeholder = "data/images/placeholder.jpg"
            if os.path.exists(placeholder):
                st.image(placeholder, use_container_width=True, caption="No Image")
            else:
                st.markdown("🖼 No image")

        in_cart_qty = st.session_state.cart.get(item["id"], {}).get("quantity", 0)
        available_stock = item["quantity"] - in_cart_qty
        if available_stock < 0:
            available_stock = 0

        st.text(f"Price: {item['price']} EGP\nStock: {available_stock}")

        qty = st.number_input(
            "Qty",
            min_value=1,
            max_value=available_stock if available_stock > 0 else 1,
            step=1,
            key=f"qty_{item['id']}"
        )

        if available_stock == 0:
            st.warning("Out of stock")
        elif st.button("➕ Add to Cart", key=f"add_{item['id']}"):
            if qty <= available_stock:
                if item["id"] in st.session_state.cart:
                    st.session_state.cart[item["id"]]["quantity"] += qty
                else:
                    st.session_state.cart[item["id"]] = {
                        "id": item["id"],
                        "name": item["name"],
                        "price": item["price"],
                        "quantity": qty
                    }
                st.success(f"✅ Added {qty} x {item['name']}")
            else:
                st.warning(f"⚠️ Cannot add {qty} items. Only {available_stock} left in stock.")

# ------------------ Cart Display ------------------ #
st.markdown("## 🛒 Cart")
if st.session_state.cart:
    cart_df = pd.DataFrame(st.session_state.cart.values())
    cart_df["total"] = cart_df["price"] * cart_df["quantity"]
    st.dataframe(cart_df, use_container_width=True)

    total = cart_df["total"].sum()
    st.markdown(f"### 💰 Total: {total} EGP")

    if st.button("🗑️ Clear Cart"):
        st.session_state.cart = {}
        st.success("🧹 Cart cleared!")

    if st.session_state.checkout_in_progress:
        st.info("🔁 Processing checkout, please wait...")
    else:
        if st.button("💳 Checkout"):
            st.session_state.checkout_in_progress = True
            st.write("🧾 Starting checkout...")
            current_products = reload_products()
            existing_ids = {p["id"] for p in current_products}

            missing = []
            for item in st.session_state.cart.values():
                if item["id"] not in existing_ids:
                    missing.append(item["id"])
            if missing:
                st.error(f"❌ Product ID(s) not found: {missing}")
                st.session_state.checkout_in_progress = False
            else:
                success = False
                attempt = 0
                max_attempts = 3

                while attempt < max_attempts and not success:
                    attempt += 1
                    try:
                        st.write(f"🚀 Attempt #{attempt} to save order...")
                        order_id = save_order(list(st.session_state.cart.values()), total)
                        success = True
                    except Exception as e:
                        st.warning(f"⚠️ Attempt #{attempt} failed: {e}")
                        if "locked" in str(e).lower() and attempt < max_attempts:
                            backoff = 0.5 * attempt
                            st.write(f"🔄 Retrying after {backoff:.1f}s...")
                            time.sleep(backoff)
                        else:
                            st.error(f"❌ Failed to save order: {e}")
                            break

                if success:
                    st.success("✅ Order complete. Receipt saved. Inventory updated.")
                    st.markdown("#### 📋 Receipt")
                    st.markdown(f"- 🧾 Order ID: `{order_id}`")
                    st.markdown(f"- 💰 Total: `{total} EGP`")
                    st.markdown(f"- 🕒 Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
                    st.session_state.cart = {}
                    st.session_state.checkout_in_progress = False
                    st.experimental_rerun()  # reload to reflect new stock
                else:
                    st.session_state.checkout_in_progress = False
else:
    st.info("🛒 Cart is empty.")
