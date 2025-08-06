import streamlit as st
import pandas as pd
import os
from datetime import datetime
from database import init_db, get_products, save_order, get_connection

# Initialize the app
st.set_page_config(page_title="🛍️ POS System", layout="wide")
st.title("🛍️ Clothing Store – Point of Sale")

# Initialize database and session state
init_db()
if "cart" not in st.session_state:
    st.session_state.cart = {}  # Format: {name: {"sizes": {size: qty}, "price": float}}
if "checkout_in_progress" not in st.session_state:
    st.session_state.checkout_in_progress = False

# Load products
products = get_products()

# Group products by name
grouped = {}
for p in products:
    grouped.setdefault(p["name"], []).append(p)

# --- Product Display ---
st.markdown("## 🛍️ Products")
for name, variants in grouped.items():
    st.markdown(f"### {name}")
    
    # Filter available variants
    available = [v for v in variants if v.get("quantity", 0) > 0]
    if not available:
        st.warning("🚫 Out of stock")
        continue
        
    # Handle size selection
    has_sizes = any(v.get("size") for v in available)
    size_state_key = f"size_{name}"
    
    if has_sizes:
        # Initialize selected size
        if size_state_key not in st.session_state:
            st.session_state[size_state_key] = available[0]["size"]
            
        # Size selector buttons
        cols = st.columns(len(available))
        for i, v in enumerate(available):
            with cols[i]:
                if st.button(v["size"], key=f"size_{name}_{v['size']}"):
                    st.session_state[size_state_key] = v["size"]
                if st.session_state[size_state_key] == v["size"]:
                    st.markdown(f"<div style='text-align:center; background:#444; color:#fff; padding:5px; border-radius:4px;'>{v['size']}</div>", unsafe_allow_html=True)
        
        selected_variant = next(v for v in available if v["size"] == st.session_state[size_state_key])
    else:
        selected_variant = available[0]
    
    # Product display columns
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        img_path = f"data/images/{selected_variant['id']}.jpg"
        st.image(img_path if os.path.exists(img_path) else "data/images/placeholder.jpg", width=120)
    
    with col2:
        st.markdown(f"**Price:** {selected_variant['price']} EGP")
        st.markdown(f"**Stock:** {sum(v['quantity'] for v in available)}")
    
    with col3:
        qty_key = f"qty_{name}"
        if qty_key not in st.session_state:
            st.session_state[qty_key] = 1
            
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("-", key=f"dec_{name}") and st.session_state[qty_key] > 1:
                st.session_state[qty_key] -= 1
        with col_b:
            st.markdown(f"<div style='text-align:center; font-size:18px;'>{st.session_state[qty_key]}</div>", unsafe_allow_html=True)
        with col_c:
            if st.button("+", key=f"inc_{name}"):
                st.session_state[qty_key] += 1
                
        if st.button("ADD TO CART", key=f"add_{name}"):
            qty = st.session_state[qty_key]
            if name not in st.session_state.cart:
                st.session_state.cart[name] = {"sizes": {}, "price": selected_variant["price"]}
            
            size = st.session_state[size_state_key] if has_sizes else None
            if size:
                st.session_state.cart[name]["sizes"][size] = st.session_state.cart[name]["sizes"].get(size, 0) + qty
            st.success(f"✅ Added {qty} x {name} ({size or 'N/A'})")

# --- Cart Display ---
st.markdown("## 🛒 Cart")
if st.session_state.cart:
    cart_items = []
    for name, item in st.session_state.cart.items():
        total_qty = sum(item["sizes"].values())
        cart_items.append({
            "name": name,
            "size": ", ".join([f"{s}({q})" for s, q in item["sizes"].items()]),
            "price": item["price"],
            "quantity": total_qty,
            "total": item["price"] * total_qty
        })
    
    st.dataframe(pd.DataFrame(cart_items), use_container_width=True)
    total = sum(item["total"] for item in cart_items)
    st.markdown(f"### 💰 Total: {total} EGP")
    
    if st.button("🗑️ Clear Cart"):
        st.session_state.cart = {}
    
    if st.button("💳 Checkout") and not st.session_state.checkout_in_progress:
        st.session_state.checkout_in_progress = True
        try:
            # Prepare cart items
            cart_for_db = []
            for name, item in st.session_state.cart.items():
                for size, qty in item["sizes"].items():
                    variant = next(
                        v for v in products 
                        if v["name"] == name and v.get("size") == size
                    )
                    cart_for_db.append({
                        "id": variant["id"],
                        "name": name,
                        "size": size,
                        "price": item["price"],
                        "quantity": qty
                    })
            
            # Save order
            order_id = save_order(cart_for_db, total)
            st.success(f"✅ Order #{order_id} complete!")
            st.session_state.cart = {}
            st.experimental_rerun()
            
        except Exception as e:
            st.error(f"❌ Checkout failed: {e}")
        finally:
            st.session_state.checkout_in_progress = False
