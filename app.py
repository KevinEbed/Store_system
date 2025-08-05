import streamlit as st
import pandas as pd
import os
from datetime import datetime

# -------------- Paths -------------- #
INVENTORY_FILE = "data/inventory.csv"
RECEIPT_FOLDER = "data/receipts"
os.makedirs(RECEIPT_FOLDER, exist_ok=True)

# -------------- CSS Injection -------------- #
def inject_custom_css():
    st.markdown("""
        <style>
            .stApp {
                background-color: #f3f6f9;
                font-family: 'Segoe UI', sans-serif;
            }
            h1 {
                color: #2c3e50;
                font-size: 2.8em;
                text-align: center;
                margin-bottom: 30px;
            }
            .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
                color: #34495e;
                margin-top: 30px;
            }
            button {
                background-color: #3498db !important;
                color: white !important;
                border-radius: 10px !important;
                padding: 0.5em 1em !important;
                font-weight: bold !important;
            }
            .stDataFrame {
                background-color: white;
                border-radius: 10px;
                padding: 10px;
                box-shadow: 0 0 10px rgba(0,0,0,0.05);
            }
            .stAlert, .stInfo, .stSuccess {
                border-radius: 8px;
                padding: 15px;
            }
            .css-1aumxhk {
                background-color: #2ecc71 !important;
                color: white !important;
                border-radius: 10px !important;
                font-weight: bold;
            }
        </style>
    """, unsafe_allow_html=True)

# -------------- Utility Functions -------------- #
def load_inventory():
    return pd.read_csv(INVENTORY_FILE)

def save_inventory(df):
    df.to_csv(INVENTORY_FILE, index=False)

def save_receipt(cart_df, total_amount):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"receipt_{now}.csv"
    path = os.path.join(RECEIPT_FOLDER, filename)
    cart_df["Total Price"] = cart_df["price"] * cart_df["quantity"]
    cart_df["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cart_df["Total Amount"] = total_amount
    cart_df.to_csv(path, index=False)

# -------------- App Config -------------- #
st.set_page_config(page_title="🧾 Clothing Store POS", layout="centered")
inject_custom_css()
st.title("🧾 Clothing Store POS System")

# Initialize cart session
if "cart" not in st.session_state:
    st.session_state.cart = []

# Load inventory
inventory = load_inventory()

# -------------- Inventory Download -------------- #
with st.expander("📥 Download Current Inventory"):
    st.download_button(
        label="Download as CSV",
        data=inventory.to_csv(index=False).encode('utf-8'),
        file_name="current_inventory.csv",
        mime="text/csv"
    )

# -------------- Inventory Display -------------- #
st.markdown("## 📦 Inventory")
st.dataframe(inventory, use_container_width=True)

# -------------- Sale Process -------------- #
st.markdown("## 🛍️ New Sale")
item_ids = inventory["id"].tolist()
item_choice = st.selectbox("Select Item ID", item_ids)

selected_item = inventory[inventory["id"] == item_choice].iloc[0]
st.markdown(f"**Item:** {selected_item['name']} | **Price:** {selected_item['price']} EGP | **Stock:** {selected_item['quantity']}")

qty = st.number_input("Quantity", min_value=1, max_value=int(selected_item["quantity"]), step=1)

if st.button("Add to Cart"):
    st.session_state.cart.append({
        "id": selected_item["id"],
        "name": selected_item["name"],
        "price": selected_item["price"],
        "quantity": qty
    })
    st.success(f"Added {qty} x {selected_item['name']}")

# -------------- Cart Display -------------- #
if st.session_state.cart:
    st.markdown("## 🛒 Cart")
    cart_df = pd.DataFrame(st.session_state.cart)
    cart_df["total"] = cart_df["price"] * cart_df["quantity"]
    st.dataframe(cart_df, use_container_width=True)

    total_amount = cart_df["total"].sum()
    st.markdown(f"### 💰 Total: {total_amount} EGP")

    if st.button("✅ Checkout"):
        # Update inventory
        for item in st.session_state.cart:
            inventory.loc[inventory["id"] == item["id"], "quantity"] -= item["quantity"]
        save_inventory(inventory)

        # Save receipt
        save_receipt(pd.DataFrame(st.session_state.cart), total_amount)
        st.success(f"✅ Sale Complete! Receipt saved. Total: {total_amount} EGP")

        # Reset cart
        st.session_state.cart = []
        st.rerun()
else:
    st.info("Cart is empty.")
