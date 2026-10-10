import os
import uuid
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

PERFUME_META = {
    "Ambre Solaire": {"brand": "BEAVER", "size_ml": "50", "notes": "Amber · Vanilla · Sandalwood"},
    "Paradoxe": {"brand": "PRADA", "size_ml": "50", "notes": "Neroli · Pink Pear · Amber"},
    "1st Collection": {"brand": "MORRA", "size_ml": "50", "notes": "Rose · Cedar · Clove · Tonka"},
    "Coco Mademoiselle Intense": {"brand": "CHANEL", "size_ml": "50", "notes": "Orange · Rose · Patchouli"},
    "Town & Country": {"brand": "CLIVE CHRISTIAN", "size_ml": "50", "notes": "Frankincense · Amber · Spice"},
    "Ani": {"brand": "NISHANE", "size_ml": "50", "notes": "Vanilla · Ginger · Cardamom"},
}
DEFAULT_META = {"brand": "", "size_ml": "50", "notes": ""}


def meta_of(name):
    return PERFUME_META.get(name, DEFAULT_META)


def get_conn():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "root"),
        database=os.environ.get("DB_NAME", "project_db"),
        port=int(os.environ.get("DB_PORT", 3306)),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def ping():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    finally:
        conn.close()


def reset_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            cur.execute("TRUNCATE TABLE order_items")
            cur.execute("TRUNCATE TABLE orders")
            cur.execute("TRUNCATE TABLE carts")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            cur.execute("UPDATE products SET STOCK = INITIAL_STOCK")
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
            cur.execute(
                "INSERT INTO users (EMAIL, NAME, PASSWORD_HASH) VALUES (%s, %s, %s)",
                (username, username, generate_password_hash(password)),
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
            cur.execute("SELECT * FROM users WHERE EMAIL = %s", (username,))
            user = cur.fetchone()
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
            products = cur.fetchall()
        for p in products:
            meta = meta_of(p["NAME"])
            p["id"] = p["PRODUCT_ID"]
            p["name"] = p["NAME"]
            p["price"] = p["PRICE"]
            p["stock"] = p["STOCK"]
            p["is_limited"] = bool(p["IS_LIMITED"])
            p["brand"] = meta["brand"]
            p["size_ml"] = meta["size_ml"]
            p["notes"] = meta["notes"]
            p["image_url"] = p["IMAGE_PATH"] or "img/p1.jpg"
        return products
    finally:
        conn.close()


def get_cart(user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.PRODUCT_ID, c.QUANTITY, p.NAME, p.PRICE, p.STOCK, p.IMAGE_PATH
                FROM carts c JOIN products p ON c.PRODUCT_ID = p.PRODUCT_ID
                WHERE c.USER_ID = %s
                ORDER BY c.CART_ID
                """,
                (user_id,),
            )
            rows = cur.fetchall()
        items = []
        total = 0
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
                    "brand": meta_of(r["NAME"])["brand"],
                    "image_url": r["IMAGE_PATH"],
                },
            })
        return items, total
    finally:
        conn.close()


def update_cart(user_id, product_id, qty):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if qty <= 0:
                cur.execute(
                    "DELETE FROM carts WHERE USER_ID = %s AND PRODUCT_ID = %s",
                    (user_id, product_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO carts (USER_ID, PRODUCT_ID, QUANTITY) VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE QUANTITY = %s
                    """,
                    (user_id, product_id, qty, qty),
                )
        conn.commit()
    finally:
        conn.close()


def add_to_cart(user_id, product_id, quantity=1):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO carts (USER_ID, PRODUCT_ID, QUANTITY) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE QUANTITY = QUANTITY + %s
                """,
                (user_id, product_id, quantity, quantity),
            )
        conn.commit()
    finally:
        conn.close()


def record_failed_order(conn, user_id, server_env, reason):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO orders
                (ORDER_NO, USER_ID, TOTAL_PRICE, STATUS, PAYMENT_STATUS, FAIL_REASON, SERVER_ENV)
            VALUES (%s, %s, 0, 'FAIL', 'FAILED', %s, %s)
            """,
            (str(uuid.uuid4()), user_id, reason[:100], server_env),
        )
    conn.commit()


def place_order(user_id, server_env):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.PRODUCT_ID, c.QUANTITY, p.NAME, p.PRICE
                FROM carts c JOIN products p ON c.PRODUCT_ID = p.PRODUCT_ID
                WHERE c.USER_ID = %s
                """,
                (user_id,),
            )
            cart_items = cur.fetchall()
            if not cart_items:
                return None, "장바구니가 비어 있습니다."

            total_price = sum(i["PRICE"] * i["QUANTITY"] for i in cart_items)

            for item in cart_items:
                cur.execute(
                    "UPDATE products SET STOCK = STOCK - %s WHERE PRODUCT_ID = %s AND STOCK >= %s",
                    (item["QUANTITY"], item["PRODUCT_ID"], item["QUANTITY"]),
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    reason = "재고 부족: " + item["NAME"]
                    record_failed_order(conn, user_id, server_env, reason)
                    return None, reason

            cur.execute(
                """
                INSERT INTO orders
                    (ORDER_NO, USER_ID, TOTAL_PRICE, STATUS, PAYMENT_METHOD, PAYMENT_STATUS, SERVER_ENV)
                VALUES (%s, %s, %s, 'SUCCESS', 'CARD', 'APPROVED', %s)
                """,
                (str(uuid.uuid4()), user_id, total_price, server_env),
            )
            order_id = cur.lastrowid

            for item in cart_items:
                cur.execute(
                    """
                    INSERT INTO order_items (ORDER_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE, SUBTOTAL)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (order_id, item["PRODUCT_ID"], item["QUANTITY"], item["PRICE"],
                     item["PRICE"] * item["QUANTITY"]),
                )

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
            cur.execute(
                """
                SELECT oi.QUANTITY AS qty, p.NAME AS name
                FROM order_items oi JOIN products p ON oi.PRODUCT_ID = p.PRODUCT_ID
                WHERE oi.ORDER_ID = %s
                """,
                (order_id,),
            )
            rows = cur.fetchall()
        items = [
            {"brand": meta_of(r["name"])["brand"], "name": r["name"], "qty": r["qty"]}
            for r in rows
        ]
        return {
            "id": o["ORDER_ID"],
            "order_no": o["ORDER_NO"],
            "total": o["TOTAL_PRICE"],
            "env": o["SERVER_ENV"],
            "status": o["STATUS"],
            "created_at": o["CREATED_AT"],
            "items": items,
        }
    finally:
        conn.close()


def recent_orders(user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ORDER_ID FROM orders
                WHERE USER_ID = %s AND STATUS = 'SUCCESS'
                ORDER BY ORDER_ID DESC LIMIT 3
                """,
                (user_id,),
            )
            order_ids = [row["ORDER_ID"] for row in cur.fetchall()]
        return [get_order(oid) for oid in order_ids]
    finally:
        conn.close()


def order_counts():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT SERVER_ENV AS env, STATUS AS status, COUNT(*) AS n
                FROM orders GROUP BY SERVER_ENV, STATUS
                """
            )
            return cur.fetchall()
    finally:
        conn.close()
