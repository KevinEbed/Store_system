import streamlit as st
import pandas as pd
import os
from datetime import datetime

# -------------- Paths -------------- #
INVENTORY_FILE = "data/inventory.csv"
RECEIPT_FOLDER = "data/receipts"
os.makedirs("data", exist_ok=True)
os.makedirs(RECEIPT_FOLDER, exist_ok=True)

# -------------- CSS Injection -------------- #
def inject_custom_css():
    st.markdown("""
        <style>
            /* General app background */
            .stApp {
                background-color: #f4f6f8;
                color: #2c3e50;  /* Default text color */
                font-family: 'Segoe UI', sans-serif;
            }

            /* Headings */
            h1, h2, h3, h4 {
                color: #2c3e50 !important;
                font-weight: 700;
            }

            /* Markdown headings */
            .stMarkdown h2, .stMarkdown h3 {
                color: #2c3e50 !important;
            }

            /* Button styling */
            button {
                background-color: #3498db !important;
                color: #ffffff !important;
                border-radius: 10px !important;
                padding: 0.6em 1em !important;
                font-weight: 600 !important;
                border: none;
            }

            /* Download buttons (Streamlit auto styles) */
            .stDownloadButton > button {
                background-color: #2ecc71 !important;
                color: white !important;
                font-weight: bold !important;
                border-radius: 10px;
            }

            /* DataFrame background */
            .stDataFrame {
                background-color: white !important;
                border-radius: 10px;
                padding: 10px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
                color: #2c3e50 !important;
            }

            /* Inputs & Selectboxes */
            .stNumberInput, .stSelectbox {
                color: #2c3e50 !important;
            }

            /* Success, Info, Warning messages */
            .stAlert, .stInfo, .stSuccess, .stWarning {
                border-radius: 10px;
                padding: 12px;
                font-size: 16px;
                color: #2c3e50;
            }

            /* Sidebar (if used) */
            .css-1d391kg {
                background-color: #f8f9fa !important;
            }
        </style>
    """, unsafe_allow_html=True)

# -------------- Utility Functions -------------- #
def ensure_inventory():
    if not os.path.exists(INVENTORY_FILE):
        sample = pd.DataFrame([
            [1, "T-Shirt", "Men", "M", 200, 10],
            [2, "Hoodie", "Unisex", "L", 300, 5],
        ], columns=["id", "name", "category", "size", "price", "quantity"])
        sample.to_csv(INVENTORY_FILE, index=False)

@st.cache_data(show_spinner=False)
def load_inventory():
    ensure_inventory()
    return pd.read_csv(INVENTORY_FILE)

def save_inventory(df):
    with st.spinner("Saving inventory..."):
        df.to_csv(INVENTORY_FILE, index=False)

def save_receipt(cart_df, total_amount):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"receipt_{now}.csv"
    path = os.path.join(RECEIPT_FOLDER, filename)
    receipt_df = cart_df.copy()
    receipt_df["Total Price"] = receipt_df["price"] * receipt_df["quantity"]
    receipt_df["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    receipt_df.loc[0, "Total Amount"] = total_amount  # put summary on top row
    receipt_df.to_csv(path, index=False)
    return path, receipt_df

# -------------- App Config -------------- #
st.set_page_config(page_title="🧾 Clothing Store POS", layout="centered")
inject_custom_css()
st.title("🧾 Clothing Store POS System")

# Initialize cart session
if "cart" not in st.session_state:
    st.session_state.cart = {}  # key: id, value: dict with name, price, quantity

# Load inventory
inventory = load_inventory()

# -------------- Inventory Download -------------- #
with st.expander("📥 Download Current Inventory"):
    st.download_button(
        label="Download as CSV",
        data=inventory.to_csv(index=False).encode("utf-8"),
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
st.markdown(
    f"**Item:** {selected_item['name']} | **Price:** {selected_item['price']} EGP | **Stock:** {selected_item['quantity']}"
)

max_qty = int(selected_item["quantity"]) if selected_item["quantity"] > 0 else 0
qty = st.number_input("Quantity", min_value=1, max_value=max_qty, step=1, disabled=(max_qty == 0))
if max_qty == 0:
    st.warning("Out of stock.")

if st.button("Add to Cart") and max_qty > 0:
    sid = int(selected_item["id"])
    existing = st.session_state.cart.get(sid)
    new_quantity = qty + (existing["quantity"] if existing else 0)
    if new_quantity > selected_item["quantity"]:
        st.warning("Cannot add more than available stock.")
    else:
        st.session_state.cart[sid] = {
            "id": sid,
            "name": selected_item["name"],
            "price": selected_item["price"],
            "quantity": new_quantity,
        }
        st.success(f"Cart updated: {new_quantity} x {selected_item['name']}")

# -------------- Cart Display -------------- #
if st.session_state.cart:
    st.markdown("## 🛒 Cart")
    cart_list = list(st.session_state.cart.values())
    cart_df = pd.DataFrame(cart_list)
    cart_df["total"] = cart_df["price"] * cart_df["quantity"]
    st.dataframe(cart_df, use_container_width=True)

    total_amount = cart_df["total"].sum()
    st.markdown(f"### 💰 Total: {total_amount} EGP")

    if st.button("✅ Checkout"):
        # Update inventory
        for item in cart_list:
            inventory.loc[inventory["id"] == item["id"], "quantity"] -= item["quantity"]
        save_inventory(inventory)

        # Save receipt and provide download
        receipt_path, receipt_df = save_receipt(pd.DataFrame(cart_list), total_amount)
        st.success(f"✅ Sale Complete! Total: {total_amount} EGP")

        with st.expander("📜 Receipt"):
            st.dataframe(receipt_df.fillna(""), use_container_width=True)
            st.download_button(
                label="Download Receipt CSV",
                data=open(receipt_path, "rb").read(),
                file_name=os.path.basename(receipt_path),
                mime="text/csv"
            )

        # Reset cart and refresh inventory view
        st.session_state.cart = {}
        st.experimental_rerun()
else:
    st.info("Cart is empty.")
