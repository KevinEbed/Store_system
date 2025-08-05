import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from database import init_db, get_products, save_order

st.set_page_config(page_title="🛍️ POS System", layout="wide")
st.title("🛍️ Clothing Store – Point of Sale")

# Initialize DB / cart
init_db()
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "checkout_in_progress" not in st.session_state:
    st.session_state.checkout_in_progress = False

def reload_products():
    return get_products()

products = reload_products()

# Group variants by product name
grouped = {}
for p in products:
    grouped.setdefault(p["name"], []).append(p)

st.markdown("## 🛍️ Products")

for name, variants in grouped.items():
    st.markdown(f"### {name}")
    for variant in variants:
        col1, col2, col3, col4 = st.columns([1.2, 1, 1, 1])
        with col1:
            image_path = f"data/images/{variant['id']}.jpg"
            if os.path.exists(image_path):
                st.image(image_path, width=100)
            else:
                placeholder = "data/images/placeholder.jpg"
                if os.path.exists(placeholder):
                    st.image(placeholder, width=100)
                else:
                    st.markdown("🖼 No image")
        with col2:
            st.markdown(f"**Size:** {variant['size']}")
            st.markdown(f"Price: {variant['price']} EGP")
            in_cart_qty = st.session_state.cart.get(variant["id"], {}).get("quantity", 0)
            available_stock = max(variant["quantity"] - in_cart_qty, 0)
            st.markdown(f"Stock: {available_stock}")
        with col3:
            qty = st.number_input(
                "Qty",
                min_value=1,
                max_value=available_stock if available_stock > 0 else 1,
                step=1,
                key=f"qty_{variant['id']}"
            )
        with col4:
            if available_stock == 0:
                st.warning("Out of stock")
            elif st.button("➕ Add to Cart", key=f"add_{variant['id']}"):
                if qty <= available_stock:
                    entry = {
                        "id": variant["id"],
                        "name": variant["name"],
                        "size": variant["size"],
                        "price": variant["price"],
                        "quantity": qty
                    }
                    if variant["id"] in st.session_state.cart:
                        st.session_state.cart[variant["id"]]["quantity"] += qty
                    else:
                        st.session_state.cart[variant["id"]] = entry
                    st.success(f"Added {qty} x {variant['name']} ({variant['size']})")
                else:
                    st.warning(f"Only {available_stock} left in stock")

st.markdown("---")
st.markdown("## 🛒 Cart")
if st.session_state.cart:
    cart_items = list(st.session_state.cart.values())
    cart_df = pd.DataFrame(cart_items)
    cart_df["total"] = cart_df["price"] * cart_df["quantity"]
    st.dataframe(cart_df[["name", "size", "price", "quantity", "total"]], use_container_width=True)

    total = cart_df["total"].sum()
    st.markdown(f"### 💰 Total: {total} EGP")

    if st.button("🗑️ Clear Cart"):
        st.session_state.cart = {}
        st.success("Cart cleared")

    if st.session_state.checkout_in_progress:
        st.info("Processing checkout...")
    elif st.button("💳 Checkout"):
        st.session_state.checkout_in_progress = True
        # Validate existence
        current_ids = {p["id"] for p in reload_products()}
        missing = [item["id"] for item in cart_items if item["id"] not in current_ids]
        if missing:
            st.error(f"Missing product IDs: {missing}")
            st.session_state.checkout_in_progress = False
        else:
            success = False
            attempt = 0
            max_attempts = 3
            while attempt < max_attempts and not success:
                attempt += 1
                try:
                    order_id = save_order(cart_items, total)
                    success = True
                except Exception as e:
                    if "locked" in str(e).lower() and attempt < max_attempts:
                        time.sleep(0.5 * attempt)
                    else:
                        st.error(f"Checkout failed: {e}")
                        break
            if success:
                st.success("Order complete. Receipt saved.")
                st.markdown(f"- **Order ID:** {order_id}")
                st.markdown(f"- **Total:** {total} EGP")
                st.markdown(f"- **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                st.session_state.cart = {}
                st.session_state.checkout_in_progress = False
                st.experimental_rerun()
            else:
                st.session_state.checkout_in_progress = False
else:
    st.info("Cart is empty.")
