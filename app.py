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

# ----------- CSS Styling ----------- #
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
            width: 250px;
            display: inline-block;
            vertical-align: top;
        }
        .product-card h4 {
            margin-bottom: 5px;
            color: #111827;
        }
        .product-card p {
            margin: 4px 0;
            color: #333;
        }
        .product-grid {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
        }
        </style>
    """, unsafe_allow_html=True)

# ----------- Setup ----------- #
st.set_page_config(page_title="🛍️ Clothing Store POS", layout="wide")
inject_css()
st.title("🛒 Clothing Store – Tap & Sell")

# ----------- Session State ----------- #
if "cart" not in st.session_state:
    st.session_state.cart = {}

# ----------- Load Inventory ----------- #
inventory = load_inventory()

# ----------- Product Grid ----------- #
st.subheader("🧾 Tap & Add Items")
st.divider()

cols = st.columns(4)
for i, item in inventory.iterrows():
    with cols[i % 4]:
        st.markdown("<div class='product-card'>", unsafe_allow_html=True)
        
        image_path = f"data/images/{item['id']}.jpg"
        if os.path.exists(image_path):
            if st.button("🖼", key=f"img_btn_{item['id']}", help="Click to select", use_container_width=True):
                pass  # Image is only visual, click not functional in this case
            st.image(image_path, use_column_width=True)
        else:
            st.image("https://via.placeholder.com/230x150?text=No+Image", use_column_width=True)

        st.markdown(f"<h4>{item['name']}</h4>", unsafe_allow_html=True)
        st.markdown(f"<p>Price: <strong>{item['price']} EGP</strong></p>", unsafe_allow_html=True)
        st.markdown(f"<p>Stock: {item['quantity']}</p>", unsafe_allow_html=True)

        qty_key = f"qty_{item['id']}"
        st.session_state[qty_key] = st.number_input(
            label="Quantity",
            min_value=1,
            max_value=int(item["quantity"]),
            step=1,
            key=qty_key
        )

        if st.button("➕ Add to Cart", key=f"add_{item['id']}"):
            item_id = int(item["id"])
            qty = st.session_state[qty_key]
            if item_id in st.session_state.cart:
                st.session_state.cart[item_id]["quantity"] += qty
            else:
                st.session_state.cart[item_id] = {
                    "id": item_id,
                    "name": item["name"],
                    "price": item["price"],
                    "quantity": qty
                }
            st.success(f"✅ Added {qty} x {item['name']} to cart!")

        st.markdown("</div>", unsafe_allow_html=True)

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

# ----------- Inventory Download ----------- #
st.divider()
st.subheader("📥 Admin: Download Updated Inventory")
st.download_button(
    label="⬇️ Download Inventory as Excel",
    data=inventory.to_csv(index=False).encode('utf-8'),
    file_name="updated_inventory.csv",
    mime="text/csv"
)
