import streamlit as st
import pandas as pd
import os
from database import init_db, get_products, save_order

st.set_page_config(page_title="🛍️ POS System", layout="wide")
st.title("🛍️ Clothing Store – Point of Sale")

# Initialize DB and session cart
init_db()
if "cart" not in st.session_state:
    st.session_state.cart = {}

# Load products from DB
products = get_products()

# Product Grid
cols = st.columns(4)
for i, item in enumerate(products):
    with cols[i % 4]:
        st.markdown(f"### {item['name']}")

        # Safe image loading with fallback
        image_path = f"data/images/{item['id']}.jpg"
        if os.path.exists(image_path):
            st.image(image_path, use_container_width=True, output_format="JPEG")
        else:
            st.image("data/images/placeholder.jpg", use_container_width=True, caption="No Image")

        st.text(f"Price: {item['price']} EGP\nStock: {item['quantity']}")

        qty = st.number_input(
            "Qty",
            min_value=1,
            max_value=item["quantity"],
            step=1,
            key=f"qty_{item['id']}"
        )

        if st.button("➕ Add to Cart", key=f"add_{item['id']}"):
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

# 🛒 Cart Display
st.subheader("🛒 Cart")
if st.session_state.cart:
    cart_df = pd.DataFrame(st.session_state.cart.values())
    cart_df["total"] = cart_df["price"] * cart_df["quantity"]
    st.dataframe(cart_df, use_container_width=True)

    total = cart_df["total"].sum()
    st.markdown(f"### 💰 Total: {total} EGP")

    if st.button("💳 Checkout"):
        # ✅ DEBUG: Check if product exists in DB
        for item in st.session_state.cart.values():
            st.write(f"🔍 Checking ID: {item['id']}")
            product_check = [p for p in get_products() if p['id'] == item['id']]
            if not product_check:
                st.error(f"❌ Product ID {item['id']} not found in DB")
                st.stop()  # ⛔ Stop checkout if product is missing

        # ✅ Proceed to save order
        save_order(list(st.session_state.cart.values()), total)
        st.success("✅ Order complete. Receipt saved. Inventory updated.")
        st.session_state.cart = {}
        st.rerun()
else:
    st.info("🛒 Cart is empty.")
