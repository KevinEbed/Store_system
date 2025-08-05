import sqlite3
from datetime import datetime

DB_NAME = "store.db"

def get_connection():
    print("🔌 Connecting to database...")
    return sqlite3.connect(DB_NAME, check_same_thread=False, timeout=10)

def init_db():
    print("🛠️ Initializing database...")
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        size TEXT,
        price INTEGER NOT NULL,
        quantity INTEGER NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        total INTEGER NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        name TEXT,
        price INTEGER,
        quantity INTEGER,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized.")

def get_products():
    print("📦 Fetching products...")
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    conn.close()
    columns = ["id", "name", "category", "size", "price", "quantity"]
    products = [dict(zip(columns, row)) for row in rows]
    print(f"📦 Loaded {len(products)} products.")
    return products

def update_product_quantity(cur, product_id, qty_sold):
    print(f"🔄 Updating stock for product ID {product_id} by -{qty_sold}")

    cur.execute("SELECT quantity FROM products WHERE id = ?", (product_id,))
    current = cur.fetchone()
    print(f"📊 Current quantity before update: {current[0] if current else 'Not Found'}")

    if current is None:
        raise Exception(f"Product ID {product_id} not found")

    if current[0] < qty_sold:
        raise Exception(f"Not enough stock for product ID {product_id}")

    cur.execute(
        "UPDATE products SET quantity = quantity - ? WHERE id = ?",
        (int(qty_sold), int(product_id))
    )

    cur.execute("SELECT quantity FROM products WHERE id = ?", (product_id,))
    updated = cur.fetchone()
    print(f"✅ Quantity after update: {updated[0] if updated else 'Not Found'}")

def save_order(cart, total_amount):
    print("💾 Saving order...")
    conn = get_connection()
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c = conn.cursor()
        print(f"🕒 Timestamp: {timestamp}, Total: {total_amount} EGP")

        c.execute("INSERT INTO orders (timestamp, total) VALUES (?, ?)", (timestamp, total_amount))
        order_id = c.lastrowid
        print(f"🧾 New order ID: {order_id}")

        for item in cart:
            print(f"🛒 Adding item: {item}")
            c.execute("""
                INSERT INTO order_items (order_id, product_id, name, price, quantity)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, item["id"], item["name"], item["price"], item["quantity"]))

            update_product_quantity(c, item["id"], item["quantity"])

        conn.commit()
        print("✅ Order saved successfully.")
        return order_id
    except Exception as e:
        conn.rollback()
        print("❌ Exception in save_order:", e)
        raise
    finally:
        conn.close()
        print("🔒 Order DB connection closed.")
