import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from database import init_db, get_products, save_order, get_connection

# ------------------ POS System ------------------ #
st.set_page_config(page_title="🛍️ POS System", layout="wide")
st.title("🛍️ Clothing Store – Point of Sale")

# ------------------ Init ------------------ #
init_db()
if "cart" not in st.session_state:
    st.session_state.cart = {}  # Store by name: {name: {"sizes": {size: quantity}, "price": float}}
if "checkout_in_progress" not in st.session_state:
    st.session_state.checkout_in_progress = False

def reload_products():
    try:
        products = get_products()  # Call without passing conn
        return products if products else []
    except Exception as e:
        st.error(f"Error loading products: {str(e)}")
        return []

products = reload_products()

# ------------------ Group by Product Name ------------------ #
grouped = {}
for p in products:
    grouped.setdefault(p["name"], []).append(p)

# ------------------ Product Display ------------------ #
st.markdown("## 🛍️ Products")
for name, variants in grouped.items():
    st.markdown(f"### {name}")

    # Filter available variants (quantity > 0)
    available_variants = [v for v in variants if v.get("quantity", 0) > 0]
    if not available_variants:
        st.warning("🚫 Out of stock for all variants.")
        continue

    # Handle products with or without sizes
    has_sizes = any(v.get("size") for v in available_variants)
    
    if has_sizes:
        # Initialize or retrieve selected size from session state
        size_state_key = f"size_{name}"
        if size_state_key not in st.session_state or st.session_state[size_state_key] not in [v["size"] for v in available_variants if v.get("size")]:
            st.session_state[size_state_key] = next((v["size"] for v in available_variants if v.get("size")), None)
        selected_size = st.session_state[size_state_key]

        # Safely find selected variant
        selected_variant = next((v for v in available_variants if v.get("size") == selected_size), available_variants[0])
        
        # Size selection with buttons
        size_cols = st.columns(len([v for v in available_variants if v.get("size")]))
        for i, variant in enumerate(available_variants):
            if variant.get("size"):  # Only show size buttons for variants with sizes
                with size_cols[i]:
                    if st.button(variant["size"], key=f"size_btn_{name}_{variant['size']}"):
                        st.session_state[size_state_key] = variant["size"]
                    if selected_size == variant["size"]:
                        st.markdown(
                            f"<div style='text-align:center; background-color:#444; color:#fff; padding:5px; border-radius:4px;'>{variant['size']}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div style='text-align:center; padding:5px; border:1px solid #666; border-radius:4px;'>{variant['size']}</div>",
                            unsafe_allow_html=True,
                        )
    else:
        # No sizes, use the first (and only) variant
        selected_variant = available_variants[0]

    # Product details (use the first variant's price as the base price)
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
        price = selected_variant.get("price", 0)
        total_quantity = sum(v["quantity"] for v in available_variants)
        st.markdown(f"**Price:** {price} EGP")
        st.markdown(f"**Total Stock Available:** {total_quantity}")

    with col3:
        qty_key = f"qty_{name}"  # Use name as key instead of id
        if qty_key not in st.session_state:
            st.session_state[qty_key] = 1

        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            if st.button("-", key=f"dec_{name}") and st.session_state[qty_key] > 1:
                st.session_state[qty_key] -= 1
        with col_b:
            st.markdown(f"<div style='text-align:center; font-size:18px;'>{st.session_state[qty_key]}</div>", unsafe_allow_html=True)
        with col_c:
            if st.button("+", key=f"inc_{name}") and st.session_state[qty_key] < total_quantity:
                st.session_state[qty_key] += 1

        if st.button("ADD TO CART", key=f"add_{name}"):
            qty = st.session_state[qty_key]
            available_stock = total_quantity
            if qty > available_stock:
                st.warning(f"Only {available_stock} left in stock across all sizes")
            else:
                # Initialize cart entry for this name if not exists
                if name not in st.session_state.cart:
                    st.session_state.cart[name] = {"sizes": {}, "price": price}
                # Update size quantities
                if selected_size:
                    st.session_state.cart[name]["sizes"][selected_size] = st.session_state.cart[name]["sizes"].get(selected_size, 0) + qty
                st.success(f"✅ Added {qty} x {name} ({selected_size or 'N/A'}) to cart")

# ------------------ Cart Display ------------------ #
st.markdown("---")
st.markdown("## 🛒 Cart")

if st.session_state.cart:
    cart_items = []
    for name, item in st.session_state.cart.items():
        total_qty = sum(item["sizes"].values())
        total_price = item["price"] * total_qty
        cart_items.append({
            "name": name,
            "size": ", ".join([f"{size} ({qty})" for size, qty in item["sizes"].items()]),
            "price": item["price"],
            "quantity": total_qty,
            "total": total_price
        })
    cart_df = pd.DataFrame(cart_items)
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

        # Build the flattened cart item list
        cart_items = []
        for name, item in st.session_state.cart.items():
            for size, qty in item["sizes"].items():
                # find variant for id
                variant = next((v for v in products if v["name"] == name and v.get("size") == size), None)
                if variant:
                    cart_items.append({
                        "id": variant["id"],
                        "name": name,
                        "size": size,
                        "price": item["price"],
                        "quantity": qty  # keep quantity here; save_order can interpret per-item quantity
                    })

        # Recompute total properly
        total = sum(ci["price"] * ci["quantity"] for ci in cart_items)

        try:
            with get_connection() as conn:
                # Enable WAL and set a reasonable busy timeout
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=30000;")  # 30 seconds

                # Reload product IDs inside same connection to avoid stale/mismatched views
                current_ids = {p["id"] for p in get_products()}  # assuming get_products uses same DB path

                # Expand cart_items into per-unit entries if save_order expects that
                expanded_items = []
                for ci in cart_items:
                    for _ in range(ci["quantity"]):
                        expanded_items.append({
                            "id": ci["id"],
                            "name": ci["name"],
                            "size": ci["size"],
                            "price": ci["price"],
                            "quantity": 1
                        })

                missing = [item["id"] for item in expanded_items if item["id"] not in current_ids]
                if missing:
                    st.error(f"❌ Product ID(s) missing: {missing}")
                    st.session_state.checkout_in_progress = False
                else:
                    success = False
                    attempt = 0
                    max_attempts = 3
                    while attempt < max_attempts and not success:
                        attempt += 1
                        try:
                            # Begin immediate transaction to acquire write lock early
                            conn.execute("BEGIN IMMEDIATE;")
                            order_id = save_order(expanded_items, total)  # ensure save_order uses the same DB file/connection internally
                            conn.commit()
                            success = True
                        except Exception as e:
                            err_str = str(e).lower()
                            conn.rollback()
                            if "locked" in err_str and attempt < max_attempts:
                                backoff = 0.5 * attempt
                                time.sleep(backoff)
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
                        st.experimental_rerun()
                    else:
                        st.session_state.checkout_in_progress = False
        except Exception as outer_e:
            st.error(f"Unexpected error during checkout: {outer_e}")
            st.session_state.checkout_in_progress = False
