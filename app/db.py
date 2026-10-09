import os
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
        cursorclass=pymysql.cursors.DictCursor
    )

def init_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    USER_ID INT AUTO_INCREMENT PRIMARY KEY,
                    USERNAME VARCHAR(255) UNIQUE NOT NULL,
                    PASSWORD_HASH VARCHAR(255) NOT NULL,
                    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    PRODUCT_ID INT AUTO_INCREMENT PRIMARY KEY,
                    NAME VARCHAR(150) NOT NULL,
                    PRICE INT NOT NULL,
                    STOCK INT NOT NULL,
                    INITIAL_STOCK INT NOT NULL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS carts (
                    USER_ID INT,
                    PRODUCT_ID INT,
                    QUANTITY INT NOT NULL,
                    PRIMARY KEY (USER_ID, PRODUCT_ID)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    ORDER_ID INT AUTO_INCREMENT PRIMARY KEY,
                    ORDER_NO VARCHAR(36) UNIQUE NOT NULL,
                    USER_ID INT NOT NULL,
                    TOTAL_PRICE INT NOT NULL,
                    STATUS VARCHAR(50) NOT NULL,
                    PAYMENT_METHOD VARCHAR(50) NOT NULL,
                    PAYMENT_STATUS VARCHAR(50) NOT NULL,
                    SERVER_ENV VARCHAR(50) NOT NULL,
                    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    ORDER_ITEM_ID INT AUTO_INCREMENT PRIMARY KEY,
                    ORDER_ID INT NOT NULL,
                    PRODUCT_ID INT NOT NULL,
                    QUANTITY INT NOT NULL,
                    UNIT_PRICE INT NOT NULL,
                    SUBTOTAL INT NOT NULL
                );
            """)
            
            cur.execute("SELECT COUNT(*) as cnt FROM products;")
            if cur.fetchone()["cnt"] == 0:
                sample_products = [
                    ("Ambre Solaire", 128000, 10, 10),
                    ("Paradoxe", 156000, 10, 10),
                    ("1st Collection", 98000, 5, 5),
                    ("Coco Mademoiselle Intense", 198000, 5, 5),
                    ("Town & Country", 420000, 1, 1),
                    ("Ani", 215000, 5, 5)
                ]
                cur.executemany("""
                    INSERT INTO products (NAME, PRICE, STOCK, INITIAL_STOCK)
                    VALUES (%s, %s, %s, %s)
                """, sample_products)
        conn.commit()
    finally:
        conn.close()

def reset_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cur.execute("TRUNCATE TABLE order_items;")
            cur.execute("TRUNCATE TABLE orders;")
            cur.execute("TRUNCATE TABLE carts;")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
            cur.execute("UPDATE products SET STOCK = INITIAL_STOCK;")
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def create_user(username, password):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            pwd_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (USERNAME, PASSWORD_HASH) VALUES (%s, %s)",
                (username, pwd_hash)
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

def check_user(username, password):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE USERNAME = %s", (username,))
            user = cur.fetchone()
        if user and check_password_hash(user["PASSWORD_HASH"], password):
            return user
        return None
    finally:
        conn.close()

def list_products():
    ui_data = {
        1: {"brand": "BEAVER", "size_ml": "50", "notes": "Amber · Vanilla · Sandalwood", "image_url": "img/p1.jpg"},
        2: {"brand": "PRADA", "size_ml": "50", "notes": "Neroli · Pink Pear · Amber", "image_url": "img/p2.jpg"},
        3: {"brand": "MORRA", "size_ml": "50", "notes": "Rose · Cedar · Clove · Tonka", "image_url": "img/p3.jpg"},
        4: {"brand": "CHANEL", "size_ml": "50", "notes": "Orange · Rose · Patchouli", "image_url": "img/p5.jpg"},
        5: {"brand": "CLIVE CHRISTIAN", "size_ml": "50", "notes": "Frankincense · Amber · Spice", "image_url": "img/p6.jpg"},
        6: {"brand": "NISHANE", "size_ml": "50", "notes": "Vanilla · Ginger · Cardamom", "image_url": "img/p7.jpg"}
    }
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products ORDER BY PRODUCT_ID")
            products = cur.fetchall()
            for p in products:
                pid = p["PRODUCT_ID"]
                meta = ui_data.get(pid, {"brand": "BRAND", "size_ml": "50", "notes": "Notes", "image_url": "img/p1.jpg"})
                p["id"] = pid
                p["name"] = p["NAME"]
                p["price"] = p["PRICE"]
                p["stock"] = p["STOCK"]
                p["brand"] = meta["brand"]
                p["size_ml"] = meta["size_ml"]
                p["notes"] = meta["notes"]
                p["image_url"] = meta["image_url"]
            return products
    finally:
        conn.close()

def get_cart(user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.PRODUCT_ID, c.QUANTITY, p.NAME, p.PRICE, p.STOCK 
                FROM carts c JOIN products p ON c.PRODUCT_ID = p.PRODUCT_ID 
                WHERE c.USER_ID = %s
            """, (user_id,))
            rows = cur.fetchall()
            items = []
            total = 0
            ui_data = {
                1: {"brand": "BEAVER"}, 2: {"brand": "PRADA"}, 3: {"brand": "MORRA"},
                4: {"brand": "CHANEL"}, 5: {"brand": "CLIVE CHRISTIAN"}, 6: {"brand": "NISHANE"}
            }
            for r in rows:
                sub = r["PRICE"] * r["QUANTITY"]
                total += sub
                items.append({
                    "qty": r["QUANTITY"],
                    "sub": sub,
                    "product": {
                        "id": r["PRODUCT_ID"],
                        "name": r["NAME"],
                        "price": r["PRICE"],
                        "stock": r["STOCK"],
                        "brand": ui_data.get(r["PRODUCT_ID"], {}).get("brand", "BRAND")
                    }
                })
            return items, total
    finally:
        conn.close()

def update_cart(user_id, product_id, qty):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if qty <= 0:
                cur.execute("DELETE FROM carts WHERE USER_ID = %s AND PRODUCT_ID = %s", (user_id, product_id))
            else:
                cur.execute("""
                    INSERT INTO carts (USER_ID, PRODUCT_ID, QUANTITY) VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE QUANTITY = %s
                """, (user_id, product_id, qty, qty))
        conn.commit()
    finally:
        conn.close()

def add_to_cart(user_id, product_id, quantity=1):
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

def place_order(user_id, server_env):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.PRODUCT_ID, c.QUANTITY, p.PRICE, p.STOCK 
                FROM carts c JOIN products p ON c.PRODUCT_ID = p.PRODUCT_ID 
                WHERE c.USER_ID = %s
            """, (user_id,))
            cart_items = cur.fetchall()
            if not cart_items:
                return None, "장바구니가 비어 있습니다."

            total_product_price = sum(item["PRICE"] * item["QUANTITY"] for item in cart_items)
            shipping = 0 if total_product_price >= 30000 else 3000
            total_price = total_product_price + shipping
            
            import uuid
            order_no = str(uuid.uuid4())

            for item in cart_items:
                cur.execute(
                    "UPDATE products SET STOCK = STOCK - %s WHERE PRODUCT_ID = %s AND STOCK >= %s",
                    (item["QUANTITY"], item["PRODUCT_ID"], item["QUANTITY"])
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    return None, "재고가 부족합니다."

            cur.execute("""
                INSERT INTO orders (ORDER_NO, USER_ID, TOTAL_PRICE, STATUS, PAYMENT_METHOD, PAYMENT_STATUS, SERVER_ENV)
                VALUES (%s, %s, %s, 'SUCCESS', 'CARD', 'APPROVED', %s)
            """, (order_no, user_id, total_price, server_env))
            order_id = cur.lastrowid

            for item in cart_items:
                subtotal = item["PRICE"] * item["QUANTITY"]
                cur.execute("""
                    INSERT INTO order_items (ORDER_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE, SUBTOTAL)
                    VALUES (%s, %s, %s, %s, %s)
                """, (order_id, item["PRODUCT_ID"], item["QUANTITY"], item["PRICE"], subtotal))

            cur.execute("DELETE FROM carts WHERE USER_ID = %s", (user_id,))
        conn.commit()
        return order_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def get_order(order_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE ORDER_ID = %s", (order_id,))
            o = cur.fetchone()
            if not o:
                return None
            ui_data = {1: {"brand": "BEAVER"}, 2: {"brand": "PRADA"}, 3: {"brand": "MORRA"}, 4: {"brand": "CHANEL"}, 5: {"brand": "CLIVE CHRISTIAN"}, 6: {"brand": "NISHANE"}}
            cur.execute("""
                SELECT oi.QUANTITY as qty, p.PRODUCT_ID, p.NAME as name
                FROM order_items oi JOIN products p ON oi.PRODUCT_ID = p.PRODUCT_ID
                WHERE oi.ORDER_ID = %s
            """, (order_id,))
            rows = cur.fetchall()
            items = []
            for r in rows:
                pid = r["PRODUCT_ID"]
                items.append({
                    "brand": ui_data.get(pid, {}).get("brand", "BRAND"),
                    "name": r["name"],
                    "qty": r["qty"]
                })
            return {
                "id": o["ORDER_ID"],
                "total": o["TOTAL_PRICE"],
                "env": o["SERVER_ENV"],
                "status": o["STATUS"],
                "created_at": o["CREATED_AT"],
                "items": items
            }
    finally:
        conn.close()

def recent_orders(user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT ORDER_ID FROM orders WHERE USER_ID = %s ORDER BY ORDER_ID DESC LIMIT 3", (user_id,))
            order_ids = [row["ORDER_ID"] for row in cur.fetchall()]
            res = []
            for oid in order_ids:
                res.append(get_order(oid))
            return res
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
