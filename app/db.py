import json
import os
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

SHIPPING_FREE_OVER = 30000
SHIPPING_FEE = 3000
STOCK_NORMAL = 30
STOCK_LIMITED = 1


def get_conn():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "root"),
        database=os.environ.get("DB_NAME", "shop"),
        port=int(os.environ.get("DB_PORT", 3306)),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )


def reset_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cur.execute("TRUNCATE TABLE orders;")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
            cur.execute(
                "UPDATE products SET stock = IF(limited = 1, %s, %s)",
                (STOCK_LIMITED, STOCK_NORMAL)
            )
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
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, generate_password_hash(password))
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
            cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
        if user and check_password_hash(user["password_hash"], password):
            return user
        return None
    finally:
        conn.close()


def list_products():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, brand, name, notes, size_ml, price, stock, limited, image_url, pos
                FROM products ORDER BY id
            """)
            return cur.fetchall()
    finally:
        conn.close()


def cart_items(cart):
    """cart: {상품id: 수량} (세션에 저장된 값). 상품 정보는 DB에서 읽어 합계를 계산한다."""
    if not cart:
        return [], 0
    ids = sorted(int(pid) for pid in cart)
    marks = ",".join(["%s"] * len(ids))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, brand, name, price, stock, image_url, pos
                FROM products WHERE id IN ({marks}) ORDER BY id
            """, ids)
            rows = cur.fetchall()
    finally:
        conn.close()

    items = []
    total = 0
    for p in rows:
        qty = int(cart[str(p["id"])])
        sub = p["price"] * qty
        total += sub
        items.append({"qty": qty, "sub": sub, "product": p})
    return items, total


def _save_order(cur, user_id, items, total, status, env):
    cur.execute(
        "INSERT INTO orders (user_id, items, total, status, env) VALUES (%s, %s, %s, %s, %s)",
        (user_id, json.dumps(items, ensure_ascii=False), total, status, env)
    )
    return cur.lastrowid


def place_order(user_id, cart, server_env):
    """성공하면 (주문id, None), 실패하면 (None, 사유). 재고 부족 시에도 fail 주문을 남긴다."""
    items, subtotal = cart_items(cart)
    if not items:
        return None, "장바구니가 비어 있습니다."

    total = subtotal if subtotal >= SHIPPING_FREE_OVER else subtotal + SHIPPING_FEE
    order_items = [
        {"id": i["product"]["id"], "brand": i["product"]["brand"], "name": i["product"]["name"],
         "qty": i["qty"], "price": i["product"]["price"]}
        for i in items
    ]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # id 순서대로 차감해서 동시 주문 시 락 순서가 엇갈리지 않게 함
            for item in order_items:
                cur.execute(
                    "UPDATE products SET stock = stock - %s WHERE id = %s AND stock >= %s",
                    (item["qty"], item["id"], item["qty"])
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    _save_order(cur, user_id, order_items, total, "fail", server_env)
                    conn.commit()
                    return None, "재고가 부족합니다."

            order_id = _save_order(cur, user_id, order_items, total, "success", server_env)
        conn.commit()
        return order_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()


def _to_order(o):
    return {
        "id": o["id"],
        "total": o["total"],
        "env": o["env"],
        "status": o["status"],
        "created_at": o["created_at"],
        "items": json.loads(o["items"]) if o["items"] else []
    }


def get_order(order_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
            o = cur.fetchone()
        return _to_order(o) if o else None
    finally:
        conn.close()


def recent_orders(user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY id DESC LIMIT 3", (user_id,))
            return [_to_order(o) for o in cur.fetchall()]
    finally:
        conn.close()


def order_counts():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT env, status, COUNT(*) AS n FROM orders GROUP BY env, status")
            return cur.fetchall()
    finally:
        conn.close()


def ping():
    conn = get_conn()
    try:
        conn.ping(reconnect=False)
    finally:
        conn.close()
