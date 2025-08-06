import sqlite3
from datetime import datetime
import time
import os

DB_NAME = "store.db"
BUSY_TIMEOUT = 5000  # 5 seconds in milliseconds

def get_connection():
    """Create and return a database connection with optimized settings"""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=BUSY_TIMEOUT/1000)
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
    conn.execute("PRAGMA busy_timeout={}".format(BUSY_TIMEOUT))
    return conn

def init_db():
    """Initialize database tables"""
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            size TEXT,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total INTEGER NOT NULL
        );
        
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
        );
        """)
        conn.commit()

def get_products():
    """Retrieve all products from database"""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM products")
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

def save_order(cart, total_amount):
    """
    Save order to database with retry logic for locked databases
    Returns order_id if successful
    """
    max_retries = 3
    retry_delay = 0.5  # seconds
    
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_connection()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Start immediate transaction
            conn.execute("BEGIN IMMEDIATE")
            
            # Insert order
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO orders (timestamp, total) VALUES (?, ?)",
                (timestamp, total_amount)
            )
            order_id = cursor.lastrowid
            
            # Insert order items and update inventory
            for item in cart:
                # Insert order item
                cursor.execute(
                    """INSERT INTO order_items 
                    (order_id, product_id, name, size, price, quantity) 
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (order_id, item["id"], item["name"], item.get("size", ""), 
                     item["price"], item["quantity"])
                )
                
                # Update product quantity
                cursor.execute(
                    """UPDATE products 
                    SET quantity = quantity - ? 
                    WHERE id = ?""",
                    (item["quantity"], item["id"]])
                
                if cursor.rowcount == 0:
                    raise ValueError(f"Product {item['id']} not found or insufficient stock")
            
            conn.commit()
            return order_id
            
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                if conn:
                    conn.rollback()
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            raise
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
