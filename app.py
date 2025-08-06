import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from database import init_db, get_products, save_order, get_connection

# Set page config with dark theme
st.set_page_config(
    page_title="🛍️ POS System",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown(
    """
    <style>
    .stApp {
        background-color: #1a1a1a;
        color: #ffffff;
    }
    .stButton>button {
        background-color: #007bff;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
    }
    .stButton>button:hover {
        background-color: #0056b3;
    }
    .product-card {
        background-color: #2a2a2a;
        border: 1px solid #444;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)
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
def render_size_buttons(name, all_sizes, available_sizes):
    st.markdown("**Size**", unsafe_allow_html=True)
    cols = st.columns(len(all_sizes))
    session_key = f"selected_size_{name}"

    # Initialize or reset selected size to an available one
    if session_key not in st.session_state or st.session_state.get(session_key) not in available_sizes:
        st.session_state[session_key] = available_sizes[0] if available_sizes else None

    for i, size in enumerate(all_sizes):
        selected = st.session_state.get(session_key) == size
        in_stock = size in available_sizes

        bg = "#00cc00" if selected and in_stock else "#2a2a2a"
        color = "#ffffff" if selected else "#cccccc"
        border = "#00cc00" if selected else "#444"
        opacity = "0.5" if not in_stock else "1"
        cursor = "not-allowed" if not in_stock else "pointer"
        content = "X" if not in_stock else size

        html = f"""
        <div style="
            background-color: {bg};
            color: {color};
            border: 2px solid {border};
            border-radius: 5px;
            padding: 8px 12px;
            text-align: center;
            font-weight: bold;
            opacity: {opacity};
            cursor: {cursor};
            display: inline-block;
            margin: 2px;
        ">
            {content}
        </div>
        """
        if in_stock:
            if cols[i].button(size, key=f"{name}_{size}", help="Select size"):
                st.session_state[session_key] = size
        else:
            cols[i].markdown(html, unsafe_allow_html=True)

# ------------------ Product Display ------------------ #
st.markdown("## 🛍️ Products")
for name, variants in grouped.items():
    available_variants = [v for v in variants if v["quantity"] > 0]
    if not available_variants:
        st.markdown(f"<div class='product-card'><h3>{name}</h3><p style='color: #ff4444;'>Out of stock for all sizes.</p></div>", unsafe_allow_html=True)
        continue

    all_sizes = sorted(set(v["size"] for v in variants))
    available_sizes = sorted(set(v["size"] for v in available_variants))
    selected_size = st.session_state.get(f"selected_size_{name}")
    selected_variant = next((v for v in available_variants if v["size"] == selected_size), None) if selected_size else available_variants[0]

    st.markdown(f"<div class='product-card'><h3>{name}</h3>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        image_path = f"data/images/{selected_variant['id']}.jpg"
        if os.path.exists(image_path):
            st.image(image_path, width=120, use_column_width=True)
        else:
            placeholder = "data/images/placeholder.jpg"
            if os.path.exists(placeholder):
                st.image(placeholder, width=120, caption="No image", use_column_width=True)
            else:
                st.markdown("🖼 No image")

    with col2:
        st.markdown(f"**Price:** {selected_variant['price']} EGP")
        st.markdown(f"**Stock:** {selected_variant['quantity']}")

    with col3:
        render_size_buttons(name, all_sizes, available_sizes)
        qty_key = f"qty_{selected_variant['id']}"
        if qty_key not in st.session_state:
            st.session_state[qty_key] = 1

        col_q1, col_q2, col_q3 = st.columns([1, 1, 1])
        with col_q1:
            st.markdown(
                f"<div style='text-align:center; font-size:18px; padding:8px; background-color:#007bff; color:white; border-radius:5px;'>-</div>",
                unsafe_allow_html=True
            )
            if st.button("-", key=f"dec_{selected_variant['id']}", help="Decrease quantity"):
                st.session_state[qty_key] = max(1, st.session_state[qty_key] - 1)
        with col_q2:
            st.markdown(
                f"<div style='text-align:center; font-size:18px; padding:8px;'>{st.session_state[qty_key]}</div>",
                unsafe_allow_html=True
            )
        with col_q3:
            st.markdown(
                f"<div style='text-align:center; font-size:18px; padding:8px; background-color:#007bff; color:white; border-radius:5px;'>+</div>",
                unsafe_allow_html=True
            )
            if st.button("+", key=f"inc_{selected_variant['id']}", help="Increase quantity"):
                st.session_state[qty_key] = min(selected_variant["quantity"], st.session_state[qty_key] + 1)

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

    st.markdown("</div>", unsafe_allow_html=True)

# ------------------ Cart Display ------------------ #
st.markdown("---")
st.markdown("## 🛒 Cart")

if st.session_state.cart:
    cart_items = list(st.session_state.cart.values())
    cart_df = pd.DataFrame(cart_items)
    cart_df["total"] = cart_df["price"] * cart_df["quantity"]
    st.markdown("<div style='background-color: #2a2a2a; padding: 10px; border-radius: 8px;'>", unsafe_allow_html=True)
    st.dataframe(cart_df[["name", "size", "price", "quantity", "total"]], use_container_width=True)
    total = cart_df["total"].sum()
    st.markdown(f"<h3 style='color: #00cc00;'>Total: {total} EGP</h3>", unsafe_allow_html=True)
    col_c1, col_c2, col_c3 = st.columns([1, 1, 1])
    with col_c1:
        if st.button("🗑️ Clear Cart"):
            st.session_state.cart = {}
            st.success("🧹 Cart cleared.")
    with col_c2:
        if st.button("💳 Checkout"):
            st.session_state.checkout_in_progress = True
            try:
                with get_connection() as conn:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA busy_timeout=60000;")
                    cursor = conn.execute("SELECT id FROM products")
                    current_ids = {row[0] for row in cursor.fetchall()}
                    missing = [item["id"] for item in cart_items if item["id"] not in current_ids]
                    if missing:
                        st.error(f"❌ Product ID(s) missing: {missing}")
                        st.session_state.checkout_in_progress = False
                    else:
                        success = False
                        attempt = 0
                        max_attempts = 5
                        while attempt < max_attempts and not success:
                            attempt += 1
                            try:
                                conn.execute("BEGIN IMMEDIATE;")
                                order_id = save_order(cart_items, total, conn)
                                conn.commit()
                                success = True
                            except Exception as e:
                                conn.rollback()
                                if "locked" in str(e).lower() and attempt < max_attempts:
                                    time.sleep(1.0 * attempt)
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
    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown("<div style='background-color: #2a2a2a; padding: 10px; border-radius: 8px;'><p>🛒 Cart is empty.</p></div>", unsafe_allow_html=True)
