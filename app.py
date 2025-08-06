import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from database import init_db, get_products, save_order

st.set_page_config(page_title="🛍️ POS System", layout="wide")
st.title("🛍️ Clothing Store – Point of Sale")

# Initialize
init_db()
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "checkout_in_progress" not in st.session_state:
    st.session_state.checkout_in_progress = False

def reload_products():
    return get_products()

products = reload_products()

# Group by name
grouped = {}
for p in products:
    grouped.setdefault(p["name"], []).append(p)

st.markdown("## 🛍️ Products")

for name, variants in grouped.items():
    st.markdown(f"### {name}")
    col1, col2 = st.columns([1, 3])

    with col1:
        img_path = f"data/images/{variants[0]['id']}.jpg"
        placeholder = "data/images/placeholder.jpg"
        if os.path.exists(img_path):
            st.image(img_path, width=120)
        elif os.path.exists(placeholder):
            st.image(placeholder, width=120)
        else:
            st.markdown("🖼 No image")

    with col2:
        # Determine if multiple sizes exist
        sizes = sorted({v["size"] for v in variants if v.get("size")})
        if sizes:
            size_key = f"size_{name}"
            selected_size = st.radio("Size", sizes, key=size_key)
            variant = next((v for v in variants if v["size"] == selected_size), None)
            if variant is None:
                st.warning("Selected size unavailable.")
                continue
        else:
            variant = variants[0]

        in_cart_qty = st.session_state.cart.get(variant["id"], {}).get("quantity", 0)
        available_stock = max(variant["quantity"] - in_cart_qty, 0)

        st.markdown(f"**Price:** {variant['price']} EGP")
        st.markdown(f"**Stock:** {available_stock}")

        qty_key = f"qty_{variant['id']}"
        if qty_key not in st.session_state:
            st.session_state[qty_key] = 1

        controls = st.columns([1,2,1])
        with controls[0]:
            if st.button("➖", key=f"dec_{variant['id']}") and st.session_state[qty_key] > 1:
                st.session_state[qty_key] -= 1
        with controls[1]:
            st.markdown(f"<div style='text-align:center'>{st.session_state[qty_key']}</div>", unsafe_allow_html=True)
        with controls[2]:
            if st.button("➕", key=f"inc_{variant['id']}") and st.session_state[qty_key] < available_stock:
                st.session_state[qty_key] += 1

        if available_stock == 0:
            st.warning("Out of stock")
        elif st.button("➕ Add to Cart", key=f"add_{variant['id']}"):
            qty_to_add = st.session_state[qty_key]
            if qty_to_add > available_stock:
                st.warning(f"Only {available_stock} left")
            else:
                entry = {
                    "id": variant["id"],
                    "name": variant["name"],
                    "size": variant.get("size", ""),
                    "price": variant["price"],
                    "quantity": qty_to_add
                }
                if variant["id"] in st.session_state.cart:
                    st.session_state.cart[variant["id"]]["quantity"] += qty_to_add
                else:
                    st.session_state.cart[variant["id"]] = entry
                st.success(f"Added {qty_to_add} x {variant['name']} ({variant.get('size','')})")

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
                st.success("Order complete.")
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
