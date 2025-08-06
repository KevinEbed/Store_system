import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from database import init_db, get_products, save_order, get_connection

st.set_page_config(page_title="🛍️ POS System", layout="wide")
st.title("🛍️ Clothing Store – Point of Sale")

# ------------------ Init ------------------ #
init_db()
if "cart" not in st.session_state:
    st.session_state.cart = {}  # Store by product_id: {id: {id, name, size, price, quantity}}
if "checkout_in_progress" not in st.session_state:
    st.session_state.checkout_in_progress = False

def reload_products():
    try:
        products = get_products()
        return products if products else []
    except Exception as e:
        st.error(f"Error loading products: {str(e)}")
        return []

products = reload_products()

# ------------------ Group by Product Name ------------------ #
grouped = {}
for p in products:
    grouped.setdefault(p["name"], []).append(p)

# ------------------ Helper: Render Size Buttons ------------------ #
def render_size_buttons(name, available_sizes):
    st.markdown("**SIZE**")
    sizes = ["XS", "S", "M", "L", "XL", "XXL"]
    col_btns = st.columns(len(sizes))
    session_key = f"selected_size_{name}"

    if session_key not in st.session_state:
        for s in sizes:
            if s in available_sizes:
                st.session_state[session_key] = s
                break

    for i, s in enumerate(sizes):
        selected = st.session_state.get(session_key) == s
        in_stock = s in available_sizes

        bg = "#333" if selected else "#fff"
        color = "#fff" if selected else "#000"
        border = "#444" if in_stock else "#ccc"
        opacity = "1" if in_stock else "0.5"
        cursor = "pointer" if in_stock else "not-allowed"

        html = f"""
        <div style="
            background-color:{bg};
            color:{color};
            border:2px solid {border};
            border-radius:6px;
            padding:8px;
            text-align:center;
            font-weight:bold;
            opacity:{opacity};
            cursor:{cursor};
        ">
        {s}
        </div>
        """

        if in_stock:
            if col_btns[i].button(s, key=f"{name}_{s}"):  # Simplified to avoid HTML button issues
                st.session_state[session_key] = s
        else:
            col_btns[i].markdown(html, unsafe_allow_html=True)

# ------------------ Product Display ------------------ #
st.markdown("## 🛍️ Products")
for name, variants in grouped.items():
    st.markdown(f"### {name}")

    available_variants = [v for v in variants if v["quantity"] > 0]
    if not available_variants:
        st.warning("🚫 Out of stock for all sizes.")
        continue

    available_sizes = [v["size"] for v in available_variants]
    render_size_buttons(name, available_sizes)

    selected_size = st.session_state.get(f"selected_size_{name}")
    selected_variant = next((v for v in available_variants if v["size"] == selected_size), None)
    if not selected_variant:
        st.warning("❌ Selected size is currently unavailable.")
        continue

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        image_path = f"data/images/{selected_variant['id']}.jpg"
        if os.path.exists(image_path):
            st.image(image_path, width=120)
        else:
            placeholder = "data/images/placeholder.jpg"
            if os.path.exists(placeholder):
                st.image(placeholder, width=120, caption="No image")
            else:
                st.markdown("🖼 No image")

    with col2:
        st.markdown(f"**Price:** {selected_variant['price']} EGP")
        st.markdown(f"**Stock Available:** {selected_variant['quantity']}")

    with col3:
        qty_key = f"qty_{selected_variant['id']}"
        if qty_key not in st.session_state:
            st.session_state[qty_key] = 1

        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            if st.button("-", key=f"dec_{selected_variant['id']}") and st.session_state[qty_key] > 1:
                st.session_state[qty_key] -= 1
        with col_b:
            st.markdown(
                f"<div style='text-align:center; font-size:18px; padding-top:10px'>{st.session_state[qty_key]}</div>",
                unsafe_allow_html=True,
            )
        with col_c:
            if st.button("+", key=f"inc_{selected_variant['id']}") and st.session_state[qty_key] < selected_variant["quantity"]:
                st.session_state[qty_key] += 1

        if st.button("➕ Add to Cart", key=f"add_{selected_variant['id']}"):
            qty = st.session_state[qty_key]
            in_cart_qty = st.session_state.cart.get(selected_variant["id"], {}).get("quantity", 0)
            available_stock = selected_variant["quantity"] - in_cart_qty
            if qty > available_stock:
                st.warning(f"Only {available_stock} left in stock")
            else:
                item = {
                    "id": selected_variant["id"],
                    "name": selected_variant["name"],
                    "size": selected_variant["size"],
                    "price": selected_variant["price"],
                    "quantity": qty
                }
                if selected_variant["id"] in st.session_state.cart:
                    st.session_state.cart[selected_variant["id"]]["quantity"] += qty
                else:
                    st.session_state.cart[selected_variant["id"]] = item
                st.success(f"✅ Added {qty} x {selected_variant['name']} ({selected_variant['size']})")

# ------------------ Cart Display ------------------ #
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
        st.success("🧹 Cart cleared.")

    if st.session_state.checkout_in_progress:
        st.info("Processing checkout...")
    elif st.button("💳 Checkout"):
        st.session_state.checkout_in_progress = True
        try:
            with get_connection() as conn:
                # Enable WAL and set busy timeout
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=60000;")  # 60 seconds

                # Reload products within the same connection to ensure consistency
                cursor = conn.execute("SELECT id FROM products")
                current_ids = {row[0] for row in cursor.fetchall()}

                # Check for missing product IDs
                missing = [item["id"] for item in cart_items if item["id"] not in current_ids]
                if missing:
                    st.error(f"❌ Product ID(s) missing: {missing}")
                    st.session_state.checkout_in_progress = False
                else:
                    success = False
                    attempt = 0
                    max_attempts = 5  # Increased retries
                    while attempt < max_attempts and not success:
                        attempt += 1
                        try:
                            conn.execute("BEGIN IMMEDIATE;")
                            order_id = save_order(cart_items, total, conn)  # Pass conn to save_order
                            conn.commit()
                            success = True
                        except Exception as e:
                            conn.rollback()
                            err_str = str(e).lower()
                            if "locked" in err_str and attempt < max_attempts:
                                time.sleep(1.0 * attempt)  # Increased backoff
                            else:
                                st.error(f"❌ Checkout failed: {e}")
                                break

                    if success:
                        st.success("✅ Order complete. Receipt saved.")
                        st.markdown(f"- 🧾 **Order ID:** `{order_id}`")
                        st.markdown(f"- 💰 **Total:** `{total} EGP`")
                        st.markdown(f"- ⏰ **Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
                        st.session_state.cart = {}
                        st.session_state.checkout_in_progress = False
                        st.rerun()
                    else:
                        st.session_state.checkout_in_progress = False
        except Exception as outer_e:
            st.error(f"Unexpected error during checkout: {outer_e}")
            st.session_state.checkout_in_progress = False
else:
    st.info("🛒 Cart is empty.")
