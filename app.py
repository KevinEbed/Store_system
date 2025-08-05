import streamlit as st
import pandas as pd
import os
import time
from database import init_db, get_products, save_order

st.set_page_config(page_title="🛍️ POS System", layout="wide")
st.title("🛍️ Clothing Store – Point of Sale")

# Initialize DB and session cart
init_db()
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "checkout_in_progress" not in st.session_state:
    st.session_state.checkout_in_progress = False

def reload_products():
    return get_products()

# Load products from DB
products = reload_products()

# Product Grid
st.markdown("## 🛍️ Products")
cols = st.columns(4)
for i, item in enumerate(products):
    with cols[i % 4]:
        st.markdown(f"### {item['name']}")

        # Safe image loading with fallback
        image_path = f"data/images/{item['id']}.jpg"
        if os.path.exists(image_path):
            st.image(image_path, use_container_width=True)
        else:
            placeholder = "data/images/placeholder.jpg"
            if os.path.exists(placeholder):
                st.image(placeholder, use_container_width=True, caption="No Image")
            else:
                st.markdown("🖼 No image")

        st.text(f"Price: {item['price']} EGP\nStock: {item['quantity']}")

        qty = st.number_input(
            "Qty",
            min_value=1,
            max_value=item["quantity"] if item["quantity"] > 0 else 1,
            step=1,
            key=f"qty_{item['id']}"
        )

        if item["quantity"] == 0:
            st.warning("Out of stock")
        elif st.button("➕ Add to Cart", key=f"add_{item['id']}"):
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
st.markdown("## 🛒 Cart")
if st.session_state.cart:
    cart_df = pd.DataFrame(st.session_state.cart.values())
    cart_df["total"] = cart_df["price"] * cart_df["quantity"]
    st.dataframe(cart_df, use_container_width=True)

    total = cart_df["total"].sum()
    st.markdown(f"### 💰 Total: {total} EGP")

    if st.session_state.checkout_in_progress:
        st.info("Processing checkout...")
    else:
        if st.button("💳 Checkout"):
            # Validate product IDs exist
            missing = []
            current_products = reload_products()
            existing_ids = {p["id"] for p in current_products}
            for item in st.session_state.cart.values():
                if item["id"] not in existing_ids:
                    missing.append(item["id"])
            if missing:
                st.error(f"❌ Product ID(s) {missing} not found in database.")
            else:
                st.session_state.checkout_in_progress = True
                success = False
                attempt = 0
                max_attempts = 3
                while attempt < max_attempts and not success:
                    try:
                        attempt += 1
                        order_id = save_order(list(st.session_state.cart.values()), total)
                        success = True
                    except Exception as e:
                        if "locked" in str(e).lower() and attempt < max_attempts:
                            backoff = 0.5 * attempt
                            time.sleep(backoff)
                        else:
                            st.error(f"❌ Failed to save order: {e}")
                            break
                if success:
                    st.success("✅ Order complete. Receipt saved. Inventory updated.")
                    # Show simple receipt summary
                    st.markdown("#### Receipt")
                    st.markdown(f"- Order ID: {order_id}")
                    st.markdown(f"- Total: {total} EGP")
                    st.markdown(f"- Time: {datetime_now := pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    st.session_state.cart = {}
                    # reload products to reflect updated stock
                    products = reload_products()
                    st.session_state.checkout_in_progress = False
                    st.experimental_rerun()
                else:
                    st.session_state.checkout_in_progress = False
else:
    st.info("🛒 Cart is empty.")
