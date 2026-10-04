import logging
import os
import time

import pymysql
from flask import Flask, Response, jsonify, render_template, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

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

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

app = Flask(__name__)

# 로그인 세션과 장바구니는 DB 없이 메모리에만 둔다
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
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS products ("
                    "id INT PRIMARY KEY, name VARCHAR(50), stock INT)"
                )
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS orders ("
                    "id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(50), "
                    "product_id INT, env VARCHAR(10), "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                )
                cur.execute("INSERT IGNORE INTO products VALUES (1, '한정판 스니커즈', 1)")
            conn.close()
            return
        except pymysql.MySQLError as e:
            logging.warning("waiting for db: %s", e)
            time.sleep(2)


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


@app.get("/api/product")
def product():
    return jsonify(fetch("SELECT id, name, stock FROM products WHERE id=1", one=True))


@app.get("/api/orders")
def recent_orders():
    rows = fetch("SELECT id, username, env, created_at FROM orders ORDER BY id DESC LIMIT 5")
    for r in rows:
        r["created_at"] = r["created_at"].strftime("%H:%M:%S")
    return jsonify(rows)


@app.post("/api/login")
def login():
    username = (request.get_json(silent=True) or {}).get("username", "").strip()
    if not username:
        return jsonify(message="이름을 입력하세요"), 400
    sessions[username] = time.time()
    sessions_gauge.labels(APP_ENV).set(len(sessions))
    return jsonify(message="로그인 완료")


@app.route("/api/cart", methods=["GET", "POST"])
def cart():
    username = request.args.get("username") or (request.get_json(silent=True) or {}).get("username")
    if username not in sessions:
        return jsonify(message="로그인이 필요합니다"), 401
    if request.method == "POST":
        carts.setdefault(username, []).append("한정판 스니커즈")
    return jsonify(items=carts.get(username, []))


@app.post("/api/order")
def order():
    username = (request.get_json(silent=True) or {}).get("username")
    if username not in sessions:
        return jsonify(message="로그인이 필요합니다"), 401
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE products SET stock = stock - 1 WHERE id=1 AND stock > 0")
            if cur.rowcount == 0:
                orders_total.labels(APP_ENV, "soldout").inc()
                return jsonify(message="품절되었습니다"), 409
            cur.execute(
                "INSERT INTO orders (username, product_id, env) VALUES (%s, 1, %s)",
                (username, APP_ENV),
            )
            order_id = cur.lastrowid
        carts.pop(username, None)
        orders_total.labels(APP_ENV, "ok").inc()
        logging.info("order %s by %s on %s", order_id, username, APP_ENV)
        return jsonify(message=f"주문 완료 (주문번호 {order_id})", order_id=order_id)
    except pymysql.MySQLError as e:
        orders_total.labels(APP_ENV, "error").inc()
        logging.error("order failed for %s: %s", username, e)
        return jsonify(message="주문 처리 중 오류가 발생했습니다"), 500
    finally:
        conn.close()


@app.post("/api/reset")
def reset():
    fetch("UPDATE products SET stock=1 WHERE id=1")
    fetch("DELETE FROM orders")
    return jsonify(message="초기화 완료")


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if INIT_DB:
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
