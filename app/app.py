import logging
import os
import secrets
import time

import pymysql
from flask import Flask, Response, jsonify, make_response, render_template, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from werkzeug.security import check_password_hash, generate_password_hash

APP_ENV = os.getenv("APP_ENV", "aws")
INIT_DB = os.getenv("INIT_DB", "1") == "1"
LOG_PATH = os.getenv("LOG_PATH", "/var/log/shop/app.log")
ENV_NAMES = {"aws": "AWS 서울", "onprem": "온프레미스"}

DB_CONFIG = dict(
    host=os.getenv("DB_HOST", "mysql"),
    user=os.getenv("DB_USER", "shop"),
    password=os.getenv("DB_PASSWORD", "shoppass"),
    database=os.getenv("DB_NAME", "shop"),
    autocommit=True,
    connect_timeout=3,
    cursorclass=pymysql.cursors.DictCursor,
)

SEED = [
    (1, "시그널 하이탑", 189000, 1, "#ff5a36", 1),
    (2, "오로라 러너", 129000, 30, "#2347ff", 0),
    (3, "미니멀 캔버스", 69000, 30, "#1f8a70", 0),
    (4, "트레일 부츠", 159000, 30, "#7a5230", 0),
    (5, "데일리 슬립온", 79000, 30, "#6b5b95", 0),
    (6, "라이트 샌들", 59000, 30, "#d99a00", 0),
]

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

# 로그인 세션과 장바구니는 메모리에만 둔다
sessions = {}
carts = {}

orders_total = Counter("shop_orders_total", "orders", ["env", "result"])
sessions_gauge = Gauge("shop_sessions", "logged in users", ["env"])
sessions_gauge.labels(APP_ENV).set(0)


def connect():
    return pymysql.connect(**DB_CONFIG)


def fetch(sql, args=None, one=False):
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone() if one else cur.fetchall()
    finally:
        conn.close()


def init_db():
    for _ in range(30):
        try:
            conn = connect()
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, "
                            "username VARCHAR(30) UNIQUE, pw_hash VARCHAR(255))")
                cur.execute("CREATE TABLE IF NOT EXISTS products (id INT PRIMARY KEY, name VARCHAR(50), "
                            "price INT, stock INT, color VARCHAR(10), limited TINYINT)")
                cur.execute("CREATE TABLE IF NOT EXISTS orders (id INT AUTO_INCREMENT PRIMARY KEY, "
                            "username VARCHAR(30), env VARCHAR(10), total INT, items VARCHAR(300), "
                            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
                cur.executemany("INSERT IGNORE INTO products VALUES (%s,%s,%s,%s,%s,%s)", SEED)
            conn.close()
            return
        except pymysql.MySQLError as e:
            logging.warning("waiting for db: %s", e)
            time.sleep(2)


def current_user():
    return sessions.get(request.cookies.get("sid"))


def cart_items(user):
    return [{"id": pid, "qty": q} for pid, q in carts.get(user, {}).items()]


def deny():
    return jsonify(message="로그인이 필요합니다"), 401


@app.get("/")
def index():
    return render_template("index.html", env=APP_ENV, env_name=ENV_NAMES.get(APP_ENV, APP_ENV))


@app.get("/health")
def health():
    try:
        fetch("SELECT 1")
        return jsonify(status="ok", env=APP_ENV)
    except pymysql.MySQLError as e:
        logging.error("health check failed: %s", e)
        return jsonify(status="fail", env=APP_ENV), 503


@app.get("/api/products")
def products():
    return jsonify(fetch("SELECT * FROM products ORDER BY id"))


@app.get("/api/orders")
def recent_orders():
    rows = fetch("SELECT id, username, env, total, created_at FROM orders ORDER BY id DESC LIMIT 5")
    for r in rows:
        r["created_at"] = r["created_at"].strftime("%H:%M:%S")
    return jsonify(rows)


def start_session(username):
    sid = secrets.token_hex(16)
    sessions[sid] = username
    sessions_gauge.labels(APP_ENV).set(len(sessions))
    resp = make_response(jsonify(username=username, cart=cart_items(username)))
    resp.set_cookie("sid", sid, httponly=True)
    return resp


@app.post("/api/signup")
def signup():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username", "").strip(), data.get("password", "")
    if not 2 <= len(username) <= 20 or len(password) < 4:
        return jsonify(message="이름은 2~20자, 비밀번호는 4자 이상이어야 합니다"), 400
    try:
        fetch("INSERT INTO users (username, pw_hash) VALUES (%s, %s)",
              (username, generate_password_hash(password)))
    except pymysql.IntegrityError:
        return jsonify(message="이미 사용 중인 이름입니다"), 409
    return start_session(username)


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    row = fetch("SELECT pw_hash FROM users WHERE username=%s", (data.get("username", ""),), one=True)
    if not row or not check_password_hash(row["pw_hash"], data.get("password", "")):
        return jsonify(message="이름 또는 비밀번호가 맞지 않습니다"), 401
    return start_session(data["username"])


@app.post("/api/logout")
def logout():
    sessions.pop(request.cookies.get("sid"), None)
    sessions_gauge.labels(APP_ENV).set(len(sessions))
    return jsonify(message="ok")


@app.get("/api/me")
def me():
    user = current_user()
    return jsonify(username=user, cart=cart_items(user)) if user else deny()


@app.post("/api/cart")
def cart():
    user = current_user()
    if not user:
        return deny()
    data = request.get_json(silent=True) or {}
    pid, delta = int(data.get("product_id", 0)), int(data.get("delta", 1))
    c = carts.setdefault(user, {})
    c[pid] = c.get(pid, 0) + delta
    if c[pid] <= 0:
        c.pop(pid)
    return jsonify(cart=cart_items(user))


@app.post("/api/order")
def order():
    user = current_user()
    if not user:
        return deny()
    cart = carts.get(user)
    if not cart:
        return jsonify(message="장바구니가 비어 있습니다"), 400
    conn = connect()
    conn.autocommit(False)
    try:
        with conn.cursor() as cur:
            total, lines = 0, []
            for pid, qty in cart.items():
                cur.execute("UPDATE products SET stock = stock - %s WHERE id=%s AND stock >= %s",
                            (qty, pid, qty))
                if cur.rowcount == 0:
                    conn.rollback()
                    orders_total.labels(APP_ENV, "soldout").inc()
                    return jsonify(message="재고가 부족한 상품이 있습니다"), 409
                cur.execute("SELECT name, price FROM products WHERE id=%s", (pid,))
                p = cur.fetchone()
                total += p["price"] * qty
                lines.append(f"{p['name']} x{qty}")
            cur.execute("INSERT INTO orders (username, env, total, items) VALUES (%s,%s,%s,%s)",
                        (user, APP_ENV, total, ", ".join(lines)))
            order_id = cur.lastrowid
        conn.commit()
        carts.pop(user, None)
        orders_total.labels(APP_ENV, "ok").inc()
        logging.info("order %s by %s on %s", order_id, user, APP_ENV)
        return jsonify(message=f"주문이 완료되었습니다 (주문번호 {order_id})", cart=[])
    except pymysql.MySQLError as e:
        conn.rollback()
        orders_total.labels(APP_ENV, "error").inc()
        logging.error("order failed for %s: %s", user, e)
        return jsonify(message="주문 처리 중 오류가 발생했습니다"), 500
    finally:
        conn.close()


@app.post("/api/reset")
def reset():
    fetch("DELETE FROM orders")
    fetch("UPDATE products SET stock = IF(limited=1, 1, 30)")
    return jsonify(message="초기화 완료")


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if INIT_DB:
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
