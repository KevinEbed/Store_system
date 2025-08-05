import sqlite3
from datetime import datetime

DB_NAME = "store.db"

# ------------------ DB Connection ------------------ #
def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False, timeout=10)

def init_db():
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

# ------------------ Product Functions ------------------ #
def get_products():
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    conn.close()
    columns = ["id", "name", "category", "size", "price", "quantity"]
    return [dict(zip(columns, row)) for row in rows]

def update_product_quantity(product_id, qty_sold):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE products SET quantity = quantity - ? WHERE id = ?",
            (int(qty_sold), int(product_id))
        )
        conn.commit()
    except Exception as e:
        print("❌ Error updating quantity:", e)
        raise
    finally:
        conn.close()

def bulk_upload_products(df, overwrite=False):
    conn = get_connection()
    try:
        c = conn.cursor()
        if overwrite:
            c.execute("DELETE FROM products")
        for _, row in df.iterrows():
            c.execute("""
                INSERT INTO products (id, name, category, size, price, quantity)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    category=excluded.category,
                    size=excluded.size,
                    price=excluded.price,
                    quantity=excluded.quantity
            """, (int(row["id"]), row["name"], row.get("category", ""), row.get("size", ""),
                  int(row["price"]), int(row["quantity"])))
        conn.commit()
    finally:
        conn.close()

# ------------------ Order Functions ------------------ #
def save_order(cart, total_amount):
    conn = get_connection()
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c = conn.cursor()
        c.execute("BEGIN")
        c.execute("INSERT INTO orders (timestamp, total) VALUES (?, ?)", (timestamp, total_amount))
        order_id = c.lastrowid

        for item in cart:
            c.execute("""
                INSERT INTO order_items (order_id, product_id, name, price, quantity)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, item["id"], item["name"], item["price"], item["quantity"]))
            update_product_quantity(item["id"], item["quantity"])

        conn.commit()
        return order_id
    except Exception as e:
        conn.rollback()
        print("❌ Error saving order:", e)
        raise
    finally:
        conn.close()

def get_order_history():
    conn = get_connection()
    cursor = conn.execute("SELECT id, timestamp, total FROM orders ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    columns = ["id", "timestamp", "total"]
    return [dict(zip(columns, row)) for row in rows]

def get_order_items(order_id):
    conn = get_connection()
    cursor = conn.execute(
        "SELECT product_id, name, price, quantity FROM order_items WHERE order_id = ?",
        (order_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    columns = ["product_id", "name", "price", "quantity"]
    return [dict(zip(columns, row)) for row in rows]
