import os
import time
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

def get_conn():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "root"),
        database=os.environ.get("DB_NAME", "project_db"),
        port=int(os.environ.get("DB_PORT", 3306)),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=3
    )

def ping():
    try:
        conn = get_conn()
        conn.close()
        return True
    except Exception:
        return False

def init_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cur.execute("TRUNCATE TABLE order_items;")
            cur.execute("TRUNCATE TABLE orders;")
            cur.execute("TRUNCATE TABLE carts;")
            cur.execute("TRUNCATE TABLE users;")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
            cur.execute("UPDATE products SET STOCK = INITIAL_STOCK;")
        conn.commit()
    finally:
        conn.close()

def reset():
    init_db()

def create_user(email, name, password):
    conn = get_conn()
    try:
        pw_hash = generate_password_hash(password)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (EMAIL, NAME, PASSWORD_HASH) VALUES (%s, %s, %s)",
                (email, name, pw_hash)
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def check_user(email, password):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cursor = cur
            cursor.execute("SELECT * FROM users WHERE EMAIL = %s", (email,))
            user = cursor.fetchone()
        if user and check_password_hash(user["PASSWORD_HASH"], password):
            return user
        return None
    finally:
        conn.close()

def list_products():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products ORDER BY PRODUCT_ID")
            return cur.fetchall()
    finally:
        conn.close()

def get_product(pid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products WHERE PRODUCT_ID = %s", (pid,))
            return cur.fetchone()
    finally:
        conn.close()

def get_cart_items(user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM carts WHERE USER_ID = %s", (user_id,))
            return cur.fetchall()
    finally:
        conn.close()

def get_cart_count(user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT SUM(QUANTITY) as cnt FROM carts WHERE USER_ID = %s", (user_id,))
            res = cur.fetchone()
            return res["cnt"] or 0
    finally:
        conn.close()

def add_to_cart(user_id, product_id, quantity):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO carts (USER_ID, PRODUCT_ID, QUANTITY)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE QUANTITY = QUANTITY + %s
            """, (user_id, product_id, quantity, quantity))
        conn.commit()
    finally:
        conn.close()

def update_cart_qty(user_id, product_id, quantity):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if quantity > 0:
                cur.execute("""
                    INSERT INTO carts (USER_ID, PRODUCT_ID, QUANTITY)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE QUANTITY = %s
                """, (user_id, product_id, quantity, quantity))
            else:
                cur.execute("DELETE FROM carts WHERE USER_ID = %s AND PRODUCT_ID = %s", (user_id, product_id))
        conn.commit()
    finally:
        conn.close()

def place_order(user_id, items, ship_fee, server_env):
    import uuid
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            total_price = sum(item["sub"] for item in items) + ship_fee
            order_no = str(uuid.uuid4())

            for item in items:
                pid = item["product"]["PRODUCT_ID"]
                qty = item["qty"]
                cur.execute(
                    "UPDATE products SET STOCK = STOCK - %s WHERE PRODUCT_ID = %s AND STOCK >= %s",
                    (qty, pid, qty)
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    return False, None

            cur.execute("""
                INSERT INTO orders (ORDER_NO, USER_ID, TOTAL_PRICE, STATUS, PAYMENT_METHOD, PAYMENT_STATUS, SERVER_ENV)
                VALUES (%s, %s, %s, 'SUCCESS', 'CARD', 'APPROVED', %s)
            """, (order_no, user_id, total_price, server_env))
            order_id = cur.lastrowid

            for item in items:
                pid = item["product"]["PRODUCT_ID"]
                qty = item["qty"]
                unit_price = item["product"]["PRICE"]
                subtotal = item["sub"]
                cur.execute("""
                    INSERT INTO order_items (ORDER_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE, SUBTOTAL)
                    VALUES (%s, %s, %s, %s, %s)
                """, (order_id, pid, qty, unit_price, subtotal))

            cur.execute("DELETE FROM carts WHERE USER_ID = %s", (user_id,))
        conn.commit()
        return True, order_no
    except Exception:
        conn.rollback()
        return False, None
    finally:
        conn.close()

def get_order_by_no(order_no, user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE ORDER_NO = %s AND USER_ID = %s", (order_no, user_id))
            order = cur.fetchone()
            if not order:
                return None
            cur.execute("""
                SELECT oi.*, p.NAME, p.IMAGE_PATH FROM order_items oi
                JOIN products p ON oi.PRODUCT_ID = p.PRODUCT_ID
                WHERE oi.ORDER_ID = %s
            """, (order["ORDER_ID"],))
            order["items"] = cur.fetchall()
            return order
    finally:
        conn.close()

def recent_orders(user_id, n=5):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM orders WHERE USER_ID = %s ORDER BY ORDER_ID DESC LIMIT %s
            """, (user_id, n))
            orders = cur.fetchall()
            for o in orders:
                cur.execute("""
                    SELECT oi.*, p.NAME FROM order_items oi
                    JOIN products p ON oi.PRODUCT_ID = p.PRODUCT_ID
                    WHERE oi.ORDER_ID = %s
                """, (o["ORDER_ID"],))
                o["items"] = cur.fetchall()
            return orders
    finally:
        conn.close()

def order_counts():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT SERVER_ENV as env, STATUS as status, COUNT(*) as n
                FROM orders GROUP BY SERVER_ENV, STATUS
            """)
            return cur.fetchall()
    finally:
        conn.close()
