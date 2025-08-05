import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ----------- Paths ----------- #
INVENTORY_FILE = "data/inventory.csv"
RECEIPT_FOLDER = "data/receipts"
os.makedirs("data/images", exist_ok=True)
os.makedirs(RECEIPT_FOLDER, exist_ok=True)

# ----------- Load & Save ----------- #
@st.cache_data
def load_inventory():
    return pd.read_csv(INVENTORY_FILE)

def save_inventory(df):
    df.to_csv(INVENTORY_FILE, index=False)

def save_receipt(cart_df, total_amount):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"receipt_{now}.csv"
    path = os.path.join(RECEIPT_FOLDER, filename)
    cart_df["Total"] = cart_df["price"] * cart_df["quantity"]
    cart_df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cart_df.loc[0, "Total Amount"] = total_amount
    cart_df.to_csv(path, index=False)

# ----------- Styling ----------- #
def inject_css():
    st.markdown("""
        <style>
        .product-card {
            background-color: #ffffff;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
            padding: 20px;
            margin: 10px;
            text-align: center;
            width: 230px;
            display: inline-block;
            vertical-align: top;
        }
        .product-card h4 {
            margin-bottom: 5px;
            color: #111827;
        }
        .product-card p {
            margin: 5px 0;
            color: #555;
        }
        .product-grid {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
        }
        </style>
    """, unsafe_allow_html=True)

# ----------- Setup ----------- #
st.set_page_config(page_title="🛒 Clothing Store POS", layout="wide")
inject_css()
st.title("🛍️ Clothing Store – Tap & Sell")

# ----------- Session State ----------- #
if "cart" not in st.session_state:
    st.session_state.cart = {}

if "selected_item_id" not in st.session_state:
    st.session_state.selected_item_id = None

# ----------- Load Inventory ----------- #
inventory = load_inventory()

# ----------- Product Grid ----------- #
st.subheader("🧾 Tap to Add Items")
st.divider()

cols = st.columns(4)
for i, item in inventory.iterrows():
    with cols[i % 4]:
        st.markdown("<div class='product-card'>", unsafe_allow_html=True)
        image_path = f"data/images/{item['id']}.jpg"
        if os.path.exists(image_path):
            st.image(image_path, use_column_width=True)
        else:
            st.image("https://via.placeholder.com/230x150?text=No+Image", use_column_width=True)

        st.markdown(f"<h4>{item['name']}</h4>", unsafe_allow_html=True)
        st.markdown(f"<p>Price: <strong>{item['price']} EGP</strong></p>", unsafe_allow_html=True)
        st.markdown(f"<p>Stock: {item['quantity']}</p>", unsafe_allow_html=True)

        if st.button(f"🛒 Select", key=f"select_{item['id']}"):
            st.session_state.selected_item_id = int(item["id"])
        st.markdown("</div>", unsafe_allow_html=True)

# ----------- Quantity Input ----------- #
if st.session_state.selected_item_id:
    selected = inventory[inventory["id"] == st.session_state.selected_item_id].iloc[0]
    st.subheader(f"🧮 Add {selected['name']} to Cart")
    qty = st.number_input("Enter quantity", min_value=1, max_value=int(selected["quantity"]), step=1, key="qty_input")

    if st.button("✅ Confirm Add"):
        sid = int(selected["id"])
        if sid in st.session_state.cart:
            st.session_state.cart[sid]["quantity"] += qty
        else:
            st.session_state.cart[sid] = {
                "id": sid,
                "name": selected["name"],
                "price": selected["price"],
                "quantity": qty
            }
        st.success(f"Added {qty} x {selected['name']} to cart.")
        st.session_state.selected_item_id = None
        st.rerun()

    if st.button("❌ Cancel"):
        st.session_state.selected_item_id = None
        st.rerun()

# ----------- Cart Section ----------- #
st.subheader("🛒 Cart")
if st.session_state.cart:
    cart_df = pd.DataFrame(list(st.session_state.cart.values()))
    cart_df["total"] = cart_df["price"] * cart_df["quantity"]
    st.dataframe(cart_df, use_container_width=True)
    total = cart_df["total"].sum()
    st.markdown(f"### 💰 Total: {total} EGP")

    if st.button("💳 Checkout"):
        for item in st.session_state.cart.values():
            inventory.loc[inventory["id"] == item["id"], "quantity"] -= item["quantity"]
        save_inventory(inventory)
        save_receipt(cart_df, total)
        st.success("✅ Order Complete! Receipt saved. Inventory updated.")
        st.session_state.cart = {}
        st.rerun()
else:
    st.info("Cart is empty.")
