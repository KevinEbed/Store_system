import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from database import init_db, get_products, save_order

st.set_page_config(page_title="🛍️ POS System", layout="wide")
st.title("🛍️ Clothing Store – Point of Sale")

# ------------------ Session State Init ------------------ #
init_db()
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "checkout_in_progress" not in st.session_state:
    st.session_state.checkout_in_progress = False

def reload_products():
    return get_products()

# ------------------ Load Products ------------------ #
products = reload_products()

# ------------------ Group by Product Name ------------------ #
grouped = {}
for p in products:
    key = p["name"]
    if key not in grouped:
        grouped[key] = []
    grouped[key].append(p)

# ------------------ Product Display ------------------ #
st.markdown("## 🛍️ Products")

for name, variants in grouped.items():
    st.markdown(f"### 🧢 {name}")
    for variant in variants:
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        with col1:
            image_path = f"data/images/{variant['id']}.jpg"
            if os.path.exists(image_path):
                st.image(image_path, width=120)
            else:
                placeholder = "data/images/placeholder.jpg"
                st.image(placeholder if os.path.exists(placeholder) else "", width=120)

        with col2:
            st.markdown(f"**Size:** {variant['size']}")
            st.markdown(f"💰 Price: `{variant['price']} EGP`")
            in_cart_qty = st.session_state.cart.get(variant["id"], {}).get("quantity", 0)
            available_stock = variant["quantity"] - in_cart_qty
            st.markdown(f"📦 Stock left: `{available_stock}`")

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
            elif st.button("➕ Add", key=f"add_{variant['id']}"):
                if qty <= available_stock:
                    if variant["id"] in st.session_state.cart:
                        st.session_state.cart[variant["id"]]["quantity"] += qty
                    else:
                        st.session_state.cart[variant["id"]] = {
                            "id": variant["id"],
                            "name": variant["name"],
                            "size": variant["size"],
                            "price": variant["price"],
                            "quantity": qty
                        }
                    st.success(f"✅ Added {qty} x {variant['name']} ({variant['size']})")
                else:
                    st.warning(f"⚠️ Only {available_stock} in stock")

st.markdown("---")

# ------------------ Cart Display ------------------ #
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
        st.success("🧹 Cart cleared!")

    if st.session_state.checkout_in_progress:
        st.info("🔁 Processing checkout, please wait...")
    else:
        if st.button("💳 Checkout"):
            st.session_state.checkout_in_progress = True
            st.write("🧾 Starting checkout...")
            current_products = reload_products()
            existing_ids = {p["id"] for p in current_products}

            # Validate product IDs
            missing = [item["id"] for item in cart_items if item["id"] not in existing_ids]
            if missing:
                st.error(f"❌ Missing products: {missing}")
                st.session_state.checkout_in_progress = False
            else:
                success = False
                attempt = 0
                max_attempts = 3

                while attempt < max_attempts and not success:
                    attempt += 1
                    try:
                        st.write(f"🚀 Attempt #{attempt} to save order...")
                        order_id = save_order(cart_items, total)
                        success = True
                    except Exception as e:
                        st.warning(f"⚠️ Attempt #{attempt} failed: {e}")
                        if "locked" in str(e).lower() and attempt < max_attempts:
                            backoff = 0.5 * attempt
                            st.write(f"🔄 Retrying in {backoff:.1f}s...")
                            time.sleep(backoff)
                        else:
                            st.error(f"❌ Checkout failed: {e}")
                            break

                if success:
                    st.success("✅ Order complete. Receipt saved.")
                    st.markdown("#### 🧾 Receipt")
                    st.markdown(f"- Order ID: `{order_id}`")
                    st.markdown(f"- Total: `{total} EGP`")
                    st.markdown(f"- Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
                    st.session_state.cart = {}
                    st.session_state.checkout_in_progress = False
                    st.rerun()
                else:
                    st.session_state.checkout_in_progress = False
else:
    st.info("🛒 Cart is empty.")
