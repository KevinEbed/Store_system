import sqlite3
from datetime import datetime

DB_NAME = "store.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False, timeout=10)

def init_db():
    conn = get_connection()
    try:
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
            size TEXT,
            price INTEGER,
            quantity INTEGER,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """)
        conn.commit()
    finally:
        conn.close()

def get_products():
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM products")
        rows = cursor.fetchall()
        columns = ["id", "name", "category", "size", "price", "quantity"]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()

def update_product_quantity(product_id, qty_sold):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT quantity FROM products WHERE id = ?", (product_id,))
        result = cur.fetchone()
        if result is None:
            raise ValueError(f"Product ID {product_id} not found.")
        if result[0] < qty_sold:
            raise ValueError(f"Insufficient stock for product ID {product_id}.")
        cur.execute(
            "UPDATE products SET quantity = quantity - ? WHERE id = ?",
            (int(qty_sold), int(product_id))
        )
        conn.commit()
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
            """, (
                int(row["id"]),
                row["name"],
                row.get("category", ""),
                row.get("size", ""),
                int(row["price"]),
                int(row["quantity"])
            ))
        conn.commit()
    finally:
        conn.close()

def save_order(cart, total_amount, conn=None):
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
        
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c = conn.cursor()
        c.execute("INSERT INTO orders (timestamp, total) VALUES (?, ?)", (timestamp, total_amount))
        order_id = c.lastrowid
        
        for item in cart:
            c.execute("""
                INSERT INTO order_items (order_id, product_id, name, size, price, quantity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                item["id"],
                item["name"],
                item.get("size", ""),
                item["price"],
                item["quantity"]
            ))
            
            # Update product quantity
            c.execute("""
                UPDATE products 
                SET quantity = quantity - ? 
                WHERE id = ? AND quantity >= ?
            """, (item["quantity"], item["id"], item["quantity"]))
            
            if c.rowcount == 0:
                raise ValueError(f"Insufficient stock for product ID {item['id']}")
                
        conn.commit()
        return order_id
    except Exception:
        conn.rollback()
        raise
    finally:
        if close_conn:
            conn.close()

def get_order_items(order_id):
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT product_id, name, size, price, quantity FROM order_items WHERE order_id = ?",
            (order_id,)
        )
        rows = cursor.fetchall()
        columns = ["product_id", "name", "size", "price", "quantity"]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()
