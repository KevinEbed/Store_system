import sqlite3
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, filename='store.log', format='%(asctime)s %(levelname)s: %(message)s')

DB_NAME = "sqlite:///store.db"

# Create SQLAlchemy engine with connection pooling
engine = create_engine(DB_NAME, poolclass=QueuePool, pool_size=5, max_overflow=10, pool_timeout=30)

def get_connection():
    return engine.connect()

def init_db():
    conn = get_connection()
    try:
        c = conn.connection.cursor()
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
        conn.connection.commit()
    except Exception as e:
        logging.error(f"Database initialization failed: {str(e)}")
        raise
    finally:
        conn.close()

def get_products():
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM products")
        rows = cursor.fetchall()
        columns = ["id", "name", "category", "size", "price", "quantity"]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logging.error(f"Error fetching products: {str(e)}")
        raise
    finally:
        conn.close()

def update_product_quantity(product_id, qty_sold):
    conn = get_connection()
    try:
        cur = conn.connection.cursor()
        cur.execute("SELECT quantity FROM products WHERE id = ?", (product_id,))
        result = cur.fetchone()
        if result is None:
            raise ValueError(f"Product ID {product_id} not found.")
        if result[0] < qty_sold:
            raise ValueError(f"Insufficient stock for product ID {product_id}. Available: {result[0]}, Requested: {qty_sold}")
        cur.execute(
            "UPDATE products SET quantity = quantity - ? WHERE id = ?",
            (int(qty_sold), int(product_id))
        )
        conn.connection.commit()
    except Exception as e:
        logging.error(f"Error updating product quantity for ID {product_id}: {str(e)}")
        conn.connection.rollback()
        raise
    finally:
        conn.close()

def bulk_upload_products(df, overwrite=False):
    conn = get_connection()
    try:
        c = conn.connection.cursor()
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
        conn.connection.commit()
    except Exception as e:
        logging.error(f"Error uploading products: {str(e)}")
        conn.connection.rollback()
        raise
    finally:
        conn.close()

def save_order(cart, total_amount):
    conn = get_connection()
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c = conn.connection.cursor()
        c.execute("PRAGMA busy_timeout=60000;")  # 60 seconds
        c.execute("BEGIN IMMEDIATE")
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
            update_product_quantity(item["id"], item["quantity"])
        conn.connection.commit()
        return order_id
    except Exception as e:
        logging.error(f"Order save failed: {str(e)}")
        conn.connection.rollback()
        raise Exception(f"Order save failed: {str(e)}")
    finally:
        conn.close()

def get_order_history():
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT id, timestamp, total FROM orders ORDER BY id DESC")
        rows = cursor.fetchall()
        columns = ["id", "timestamp", "total"]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logging.error(f"Error fetching order history: {str(e)}")
        raise
    finally:
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
    except Exception as e:
        logging.error(f"Error fetching order items for order {order_id}: {str(e)}")
        raise
    finally:
        conn.close()
