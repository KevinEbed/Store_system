import streamlit as st
from database import init_db, get_products, save_order
import pandas as pd
import os

# ---------- Setup ---------- #
st.set_page_config(page_title="🛒 POS (DB Edition)", layout="wide")

if "cart" not in st.session_state:
    st.session_state.cart = {}

init_db()

# ---------- Load Products ---------- #
inventory = get_products()

st.title("🛍️ Clothing Store – POS with SQLite")

# ---------- Product Cards ---------- #
cols = st.columns(4)
for i, item in enumerate(inventory):
    with cols[i % 4]:
        st.markdown("### " + item["name"])
        st.text(f"Price: {item['price']} EGP\nStock: {item['quantity']}")
        qty = st.number_input("Qty", min_value=1, max_value=item["quantity"], key=f"qty_{item['id']}")
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
            st.success(f"{qty} x {item['name']} added to cart!")

# ---------- Cart Section ---------- #
st.subheader("🛒 Cart")
if st.session_state.cart:
    cart_df = pd.DataFrame(st.session_state.cart.values())
    cart_df["total"] = cart_df["price"] * cart_df["quantity"]
    st.dataframe(cart_df, use_container_width=True)
    total = cart_df["total"].sum()
    st.markdown(f"### 💰 Total: {total} EGP")

    if st.button("💳 Checkout"):
        save_order(list(st.session_state.cart.values()), total)
        st.success("✅ Order placed, inventory updated.")
        st.session_state.cart = {}
        st.rerun()
else:
    st.info("Cart is empty.")

# ---------- Download Inventory ---------- #
st.divider()
if st.button("📥 Download Updated Inventory"):
    products_df = pd.DataFrame(get_products())
    st.download_button("⬇️ Download Excel", data=products_df.to_csv(index=False), file_name="inventory_db.csv")
