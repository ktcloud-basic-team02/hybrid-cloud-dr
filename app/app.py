import os
import re
import secrets
import time
import logging
import uuid
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, Response, session
from werkzeug.security import generate_password_hash, check_password_hash
import db

APP_ENV = os.environ.get("APP_ENV", "aws")
ENV_LABEL = {"aws": "AWS · Seoul", "onprem": "On-premise"}

LOG_PATH = os.environ.get("LOG_PATH", "/var/log/shop/app.log")
try:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
except OSError:
    handler = logging.FileHandler("app.log", encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log = logging.getLogger("shop")
log.setLevel(logging.INFO)
log.addHandler(handler)

stream = logging.StreamHandler()
stream.setFormatter(handler.formatter)
log.addHandler(stream)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")
RESET_TOKEN = os.environ.get("RESET_TOKEN", "")

REQ = {}
LAT = {"sum": 0.0, "count": 0}
SKIP = ("/static", "/health", "/metrics", "/api")

if os.environ.get("INIT_DB") == "1":
    db.init_db()


@app.before_request
def start_timer():
    g.t0 = time.time()


@app.after_request
def save_session(resp):
    if not request.path.startswith("/metrics"):
        k = (request.method, resp.status_code)
        REQ[k] = REQ.get(k, 0) + 1
        LAT["sum"] += time.time() - g.get("t0", time.time())
        LAT["count"] += 1
    return resp


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


def get_cart_items(user_id):
    items = db.get_cart_items(user_id)
    formatted = []
    total = 0
    for item in items:
        p = db.get_product(item["PRODUCT_ID"])
        if p:
            sub = p["PRICE"] * item["QUANTITY"]
            total += sub
            formatted.append(dict(product=p, qty=item["QUANTITY"], sub=sub))
    return formatted, total


@app.context_processor
def common():
    user_id = session.get("user_id")
    cart_count = db.get_cart_count(user_id) if user_id else 0
    user = {"id": user_id, "email": session.get("user_email"), "name": session.get("user_name")} if user_id else None
    return dict(cart_count=cart_count, user=user, env=APP_ENV, env_label=ENV_LABEL.get(APP_ENV, APP_ENV))


@app.template_filter("won")
def won(v):
    return f"{v:,}원"


@app.route("/")
def index():
    return redirect(url_for("products"))


@app.route("/health")
def health():
    if db.ping():
        return jsonify(status="ok", env=APP_ENV)
    return jsonify(status="db_down", env=APP_ENV), 503


@app.route("/metrics")
def metrics():
    lines = ["# HELP shop_orders_total 주문 수 (환경, 결과별)", "# TYPE shop_orders_total counter"]
    db_up = 1
    try:
        for r in db.order_counts():
            lines.append(f'shop_orders_total{{env="{r["env"]}",result="{r["status"]}"}} {r["n"]}')
    except Exception:
        db_up = 0
        log.exception("metrics: DB 조회 실패")
    lines += ["# HELP shop_db_up DB 연결 상태 (1=정상, 0=끊김)", "# TYPE shop_db_up gauge",
              f"shop_db_up {db_up}"]
    lines += ["# HELP shop_info 앱이 실행 중인 환경", "# TYPE shop_info gauge",
              f'shop_info{{env="{APP_ENV}"}} 1']
    lines += ["# HELP shop_sessions 로그인 중인 사용자 수", "# TYPE shop_sessions gauge",
              f"shop_sessions {1 if session.get('user_id') else 0}"]
    lines += ["# HELP shop_requests_total HTTP 요청 수", "# TYPE shop_requests_total counter"]
    for (m, st), n in REQ.items():
        lines.append(f'shop_requests_total{{method="{m}",status="{st}"}} {n}')
    lines += ["# TYPE shop_request_seconds_sum counter", f"shop_request_seconds_sum {LAT['sum']}",
              "# TYPE shop_request_seconds_count counter", f"shop_request_seconds_count {LAT['count']}"]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@app.route("/api/reset", methods=["POST", "GET"])
def api_reset():
    if RESET_TOKEN and request.args.get("token") != RESET_TOKEN:
        return jsonify(status="forbidden"), 403
    db.reset()
    log.warning("reset: 데이터 초기화, 재고 원복")
    return jsonify(status="reset")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"].strip()
        name = request.form["name"].strip()
        password = request.form["password"]

        if not email or not name or len(password) < 4:
            flash("모든 필드를 올바르게 입력해주세요. (비밀번호 4자 이상)")
        elif db.create_user(email, name, password):
            log.info("signup: %s", email)
            flash("가입이 완료됐습니다. 로그인해 주세요.")
            return redirect(url_for("login"))
        else:
            flash("이미 사용 중인 이메일입니다.")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]
        u = db.check_user(email, password)
        if u:
            session["user_id"] = u["USER_ID"]
            session["user_email"] = u["EMAIL"]
            session["user_name"] = u["NAME"]
            log.info("login: %s", email)
            return redirect(request.args.get("next") or url_for("products"))
        log.info("login 실패: %s", email)
        flash("이메일 또는 비밀번호가 올바르지 않습니다.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("products"))


@app.route("/products")
def products():
    user_id = session.get("user_id")
    recent = db.recent_orders(user_id) if user_id else []
    return render_template("products.html", products=db.list_products(), recent=recent)


@app.route("/cart")
@login_required
def cart():
    items, total = get_cart_items(session["user_id"])
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:pid>", methods=["POST"])
@login_required
def cart_add(pid):
    p = db.get_product(pid)
    if not p or p["STOCK"] < 1:
        flash("품절된 상품입니다.")
        return redirect(url_for("products"))
    db.add_to_cart(session["user_id"], pid, 1)
    return redirect(url_for("cart"))


@app.route("/cart/update/<int:pid>", methods=["POST"])
@login_required
def cart_update(pid):
    qty = int(request.form.get("qty", 0))
    db.update_cart_qty(session["user_id"], pid, qty)
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    user_id = session["user_id"]
    items, total = get_cart_items(user_id)
    if not items:
        return redirect(url_for("cart"))
    if request.method == "POST":
        ship = total if total >= 30000 else total + 3000
        ok, order_no = db.place_order(user_id, items, ship, APP_ENV)
        log.info("order #%s %s (%s) user=%s", order_no, "success" if ok else "fail", APP_ENV, session["user_email"])
        if not ok:
            flash("재고가 부족해 주문에 실패했습니다.")
            return redirect(url_for("products"))
        return redirect(url_for("order_done", order_no=order_no))
    return render_template("checkout.html", items=items, total=total)


@app.route("/order/<order_no>")
@login_required
def order_done(order_no):
    o = db.get_order_by_no(order_no, session["user_id"])
    if not o:
        return redirect(url_for("products"))
    return render_template("order.html", o=o)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
