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
    .product-card {
        background-color: #2a2a2a;
        border: 1px solid #444;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
    }
    .warning-box {
        background-color: #ff4444;
        color: white;
        padding: 10px;
        border-radius: 4px;
        margin-top: 10px;
        display: inline-block;
    }
    .size-button {
        background-color: transparent;
        color: #ffffff;
        border: 2px solid #ffffff;
        border-radius: 5px;
        padding: 8px 12px;
        text-align: center;
        font-weight: bold;
        margin: 0 5px 5px 0;
        cursor: pointer;
        transition: all 0.3s;
        min-width: 40px;
    }
    .size-button.selected {
        background-color: #00cc00;
        border-color: #00cc00;
    }
    .size-button.out-of-stock {
        opacity: 0.5;
        cursor: not-allowed;
        border-color: #666666;
    }
    .qty-button {
        background-color: transparent;
        color: white;
        border: 2px solid white;
        border-radius: 5px;
        width: 40px;
        height: 40px;
        font-size: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
    }
    .qty-button:hover {
        background-color: #333333;
    }
    .qty-display {
        background-color: transparent;
        color: white;
        border: 2px solid white;
        border-radius: 5px;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 5px;
    }
    .add-to-cart-btn {
        background-color: #000000;
        color: white;
        border: 2px solid white;
        border-radius: 5px;
        padding: 10px;
        font-weight: bold;
        width: 100%;
        margin-top: 10px;
        cursor: pointer;
    }
    .add-to-cart-btn:hover {
        background-color: #333333;
    }
    .size-qty-section {
        margin-top: 10px;
    }
    .product-info {
        margin-bottom: 10px;
    }
    .product-title {
        margin-bottom: 5px;
    }
.stSelectbox {
        width: 80px !important; /* Shorter width */
        border-radius: 10px !important;
        background-color: #2a2a2a !important;
        color: #fff !important;
        border: 2px solid #444 !important;
    }
    .stSelectbox > div > div {
        background-color: #2a2a2a !important;
        color: #fff !important;
    }
    .stSelectbox label {
        color: #fff !important;
        font-size: 14px !important;
    }
    /* Hide search/filter input (simulating non-searchable) */
    .stSelectbox div[role="combobox"] {
        padding: 0 !important;
    }
    .stSelectbox div[role="listbox"] {
        max-height: 150px !important; /* Limit dropdown height */
    }
    </style>
    """,
    unsafe_allow_html=True
)
st.title("🛍️ Products")

# ------------------ Init ------------------ #
init_db()
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "checkout_in_progress" not in st.session_state:
    st.session_state.checkout_in_progress = False
if "warnings" not in st.session_state:
    st.session_state.warnings = {}
if "quantities" not in st.session_state:
    st.session_state.quantities = {}

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

# ------------------ Helper: Render Size Buttons and Quantities ------------------ #
# Inside render_size_quantities function
def render_size_quantities(name, variants):
    available_variants = [v for v in variants if v["quantity"] > 0]
    has_sizes = len(set(v["size"] for v in variants)) > 1
    
    if has_sizes:
        st.markdown("**Size & Quantity**", unsafe_allow_html=True)
        all_sizes = sorted(set(v["size"] for v in variants))
        available_sizes = sorted(set(v["size"] for v in available_variants))
        session_key = f"selected_size_{name}"
        qty_key_prefix = f"qty_{name}_"

        # Initialize selected size
        if session_key not in st.session_state:
            st.session_state[session_key] = available_sizes[0] if available_sizes else None

        # Use columns to place size and quantity side by side
        col1, col2 = st.columns(2)

        with col1:
            # Size dropdown (freely selectable with update trigger)
            selected_size = st.selectbox("Size:", available_sizes, index=available_sizes.index(st.session_state[session_key]) if st.session_state[session_key] in available_sizes else 0, key=f"size_select_{name}", help="Select a size")
            if selected_size != st.session_state[session_key]:
                st.session_state[session_key] = selected_size
                # Clear previous quantity to force recalculation
                for key in list(st.session_state.quantities.keys()):
                    if key.startswith(qty_key_prefix):
                        del st.session_state.quantities[key]
                st.rerun()

        with col2:
            # Quantity dropdown for selected size with dynamic stock
            if st.session_state[session_key] and st.session_state[session_key] in available_sizes:
                variant = next(v for v in variants if v["size"] == st.session_state[session_key])
                qty_key = f"qty_{name}_{st.session_state[session_key]}"
                if qty_key not in st.session_state.quantities:
                    st.session_state.quantities[qty_key] = 1
                
                quantities = list(range(1, variant["quantity"] + 1))
                selected_qty = st.selectbox("Qty:", quantities, index=quantities.index(st.session_state.quantities[qty_key]) if st.session_state.quantities[qty_key] in quantities else 0, key=f"qty_select_{name}_{st.session_state[session_key]}")
                st.session_state.quantities[qty_key] = selected_qty

    else:
        # For items without sizes
        variant = variants[0]
        qty_key = f"qty_{name}"
        if qty_key not in st.session_state.quantities:
            st.session_state.quantities[qty_key] = 1
            
        st.markdown("**Quantity**", unsafe_allow_html=True)
        quantities = list(range(1, variant["quantity"] + 1))
        selected_qty = st.selectbox("Qty:", quantities, index=quantities.index(st.session_state.quantities[qty_key]) if st.session_state.quantities[qty_key] in quantities else 0, key=f"qty_select_{name}")
        st.session_state.quantities[qty_key] = selected_qty
# ------------------ Product Display ------------------ #
for name, variants in grouped.items():
    available_variants = [v for v in variants if v["quantity"] > 0]
    
    st.markdown(f"<div class='product-card'><h3 class='product-title'>{name}</h3>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        image_path = f"data/images/{name.replace(' ', '_').lower()}.jpg"
        if os.path.exists(image_path):
            st.image(image_path, width=120, use_container_width=True)
        else:
            st.image("data/images/placeholder.jpg", width=120, use_container_width=True)

    with col2:
        st.markdown('<div class="product-info">', unsafe_allow_html=True)
        st.markdown(f"**Price:** {variants[0]['price']} EGP")
        selected_size = st.session_state.get(f"selected_size_{name}")
        if selected_size:
            stock = next(v["quantity"] for v in variants if v["size"] == selected_size)
        else:
            stock = sum(v["quantity"] for v in variants)
        st.markdown(f"**Stock:** {stock}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        render_size_quantities(name, variants)
        
        if available_variants:
            if len(variants) > 1:  # Has sizes
                selected_size = st.session_state.get(f"selected_size_{name}")
                selected_variant = next((v for v in available_variants if v["size"] == selected_size), None)
            else:  # No sizes
                selected_variant = available_variants[0]
                qty_key = f"qty_{name}"
            
            if selected_variant:
                if st.button("Add to Cart", key=f"add_{selected_variant['id']}"):
                    qty = st.session_state.quantities.get(
                        f"qty_{name}_{selected_variant['size']}" if len(variants) > 1 else f"qty_{name}", 
                        1
                    )
                    in_cart_qty = st.session_state.cart.get(selected_variant["id"], {}).get("quantity", 0)
                    available_stock = selected_variant["quantity"] - in_cart_qty
                    
                    if qty <= available_stock:
                        item = {
                            "id": selected_variant["id"],
                            "name": selected_variant["name"],
                            "size": selected_variant["size"] if len(variants) > 1 else "",
                            "price": selected_variant["price"],
                            "quantity": qty
                        }
                        if selected_variant["id"] in st.session_state.cart:
                            st.session_state.cart[selected_variant["id"]]["quantity"] += qty
                        else:
                            st.session_state.cart[selected_variant["id"]] = item
                        # Removed warning message setting
                    else:
                        # Optionally handle out-of-stock case without warning
                        pass

    if st.session_state.warnings.get(name):
        st.markdown(f"<div class='warning-box'>{st.session_state.warnings[name]}</div>", unsafe_allow_html=True)
        if st.button("✖ Clear Warning", key=f"clear_warning_{name}"):
            st.session_state.warnings[name] = ""
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
                        st.session_state.warnings["checkout"] = f"❌ Product ID(s) missing: {missing}"
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
                                    st.session_state.warnings["checkout"] = f"❌ Checkout failed: {e}"
                                    break
                        if success:
                            st.success("✅ Order complete. Receipt saved.")
                            st.markdown(f"- 🧾 **Order ID:** `{order_id}`")
                            st.markdown(f"- 💰 **Total:** `{total} EGP`")
                            st.markdown(f"- ⏰ **Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
                            st.session_state.cart = {}
                            st.session_state.checkout_in_progress = False
                            st.session_state.warnings["checkout"] = ""
                            st.rerun()
                        else:
                            st.session_state.checkout_in_progress = False
            except Exception as outer_e:
                st.session_state.warnings["checkout"] = f"Unexpected error during checkout: {outer_e}"
                st.session_state.checkout_in_progress = False
    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown("<div style='background-color: #2a2a2a; padding: 10px; border-radius: 8px;'><p>🛒 Cart is empty.</p></div>", unsafe_allow_html=True)

if st.session_state.warnings.get("checkout"):
    st.markdown(f"<div class='warning-box'>{st.session_state.warnings['checkout']}</div>", unsafe_allow_html=True)
    if st.button("✖ Clear Checkout Warning", key="clear_checkout_warning"):
        st.session_state.warnings["checkout"] = ""
