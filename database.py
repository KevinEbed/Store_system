import sqlite3
from datetime import datetime
import time

DB_NAME = "store.db"
BUSY_TIMEOUT = 5000  # 5 seconds

def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=BUSY_TIMEOUT/1000)
    conn.execute("PRAGMA journal_mode=WAL")  # Enable Write-Ahead Logging
    conn.execute("PRAGMA busy_timeout={}".format(BUSY_TIMEOUT))
    return conn

def save_order(cart, total_amount):
    conn = None
    max_retries = 3
    retry_delay = 0.1  # seconds
    
    for attempt in range(max_retries):
        try:
            conn = get_connection()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Start transaction
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
                    (
                        order_id,
                        item["id"],
                        item["name"],
                        item.get("size", ""),
                        item["price"],
                        item["quantity"]
                    )
                )
                
                # Update product quantity
                cursor.execute(
                    """UPDATE products 
                    SET quantity = quantity - ? 
                    WHERE id = ? AND quantity >= ?""",
                    (item["quantity"], item["id"], item["quantity"])
                )
                
                if cursor.rowcount == 0:
                    raise ValueError(f"Insufficient stock for product ID {item['id']}")
            
            conn.commit()
            return order_id
            
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                if conn:
                    conn.rollback()
                    conn.close()
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
