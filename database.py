import sqlite3
from datetime import datetime

DB_NAME = "store.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT,
        category TEXT,
        size TEXT,
        price INTEGER,
        quantity INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        total INTEGER
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

def get_products():
    conn = get_connection()
    df = conn.execute("SELECT * FROM products").fetchall()
    columns = ["id", "name", "category", "size", "price", "quantity"]
    conn.close()
    return [dict(zip(columns, row)) for row in df]

def update_product_quantity(product_id, qty_sold):
    conn = get_connection()
    conn.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (qty_sold, product_id))
    conn.commit()
    conn.close()

def save_order(cart, total_amount):
    conn = get_connection()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = conn.cursor()
    c.execute("INSERT INTO orders (timestamp, total) VALUES (?, ?)", (timestamp, total_amount))
    order_id = c.lastrowid

    for item in cart:
        c.execute("""
        INSERT INTO order_items (order_id, product_id, name, price, quantity)
        VALUES (?, ?, ?, ?, ?)
        """, (order_id, item["id"], item["name"], item["price"], item["quantity"]))
        update_product_quantity(item["id"], item["quantity"])

    conn.commit()
    conn.close()
