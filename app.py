import streamlit as st
import pandas as pd
from database import init_db, get_products, save_order

st.set_page_config(page_title="🛍️ POS System", layout="wide")
st.title("🛍️ Clothing Store – Point of Sale")

init_db()

if "cart" not in st.session_state:
    st.session_state.cart = {}

products = get_products()

cols = st.columns(4)
for i, item in enumerate(products):
    with cols[i % 4]:
        st.markdown(f"### {item['name']}")
        st.image(f"data/images/{item['id']}.jpg", use_column_width=True, output_format="JPEG")
        st.text(f"Price: {item['price']} EGP\nStock: {item['quantity']}")
        qty = st.number_input("Qty", min_value=1, max_value=item["quantity"], step=1, key=f"qty_{item['id']}")
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

st.subheader("🛒 Cart")
if st.session_state.cart:
    cart_df = pd.DataFrame(st.session_state.cart.values())
    cart_df["total"] = cart_df["price"] * cart_df["quantity"]
    st.dataframe(cart_df, use_container_width=True)
    total = cart_df["total"].sum()
    st.markdown(f"### 💰 Total: {total} EGP")

    if st.button("💳 Checkout"):
        save_order(list(st.session_state.cart.values()), total)
        st.success("✅ Order complete. Receipt saved. Inventory updated.")
        st.session_state.cart = {}
        st.rerun()
else:
    st.info("🛒 Cart is empty.")
