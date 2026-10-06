import os
import re
import secrets
import time
import logging
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, Response
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

SESSIONS = {}
REQ = {}
LAT = {"sum": 0.0, "count": 0}
SKIP = ("/static", "/health", "/metrics", "/api")

if os.environ.get("INIT_DB") == "1":
    db.init_db()


@app.before_request
def load_session():
    g.sid, g.new = request.cookies.get("sid"), False
    if request.path.startswith(SKIP):
        g.s = {"user": None, "cart": {}}
        return
    if g.sid not in SESSIONS:
        g.sid, g.new = secrets.token_hex(16), True
        SESSIONS[g.sid] = {"user": None, "cart": {}}
    g.s = SESSIONS[g.sid]


@app.before_request
def start_timer():
    g.t0 = time.time()


@app.after_request
def save_session(resp):
    if g.get("new"):
        resp.set_cookie("sid", g.sid, httponly=True, samesite="Lax")
    if not request.path.startswith("/metrics"):
        k = (request.method, resp.status_code)
        REQ[k] = REQ.get(k, 0) + 1
        LAT["sum"] += time.time() - g.get("t0", time.time())
        LAT["count"] += 1
    return resp


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not g.s["user"]:
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


def cart_items():
    items = []
    for pid, qty in g.s["cart"].items():
        p = db.get_product(pid)
        if p:
            items.append(dict(product=p, qty=qty, sub=p["price"] * qty))
    return items, sum(i["sub"] for i in items)


@app.context_processor
def common():
    return dict(cart_count=sum(g.s["cart"].values()), user=g.s["user"],
                env=APP_ENV, env_label=ENV_LABEL.get(APP_ENV, APP_ENV))


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
    try:
        for r in db.order_counts():
            lines.append(f'shop_orders_total{{env="{r["env"]}",result="{r["status"]}"}} {r["n"]}')
    except Exception:
        log.exception("metrics: DB 조회 실패")
    lines += ["# HELP shop_sessions 로그인 중인 사용자 수", "# TYPE shop_sessions gauge",
              f"shop_sessions {sum(1 for s in SESSIONS.values() if s['user'])}"]
    lines += ["# HELP shop_requests_total HTTP 요청 수", "# TYPE shop_requests_total counter"]
    for (m, st), n in REQ.items():
        lines.append(f'shop_requests_total{{method="{m}",status="{st}"}} {n}')
    lines += ["# TYPE shop_request_seconds_sum counter", f"shop_request_seconds_sum {LAT['sum']}",
              "# TYPE shop_request_seconds_count counter", f"shop_request_seconds_count {LAT['count']}"]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@app.route("/api/reset", methods=["POST", "GET"])
def api_reset():
    db.reset()
    log.warning("reset: 주문 삭제, 재고 초기화")
    return jsonify(status="reset")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        u, pw = request.form["username"].strip(), request.form["password"]
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", u) or len(pw) < 4:
            flash("아이디는 영문/숫자 3~20자, 비밀번호는 4자 이상이어야 합니다.")
        elif db.create_user(u, pw):
            log.info("signup: %s", u)
            flash("가입이 완료됐습니다. 로그인해 주세요.")
            return redirect(url_for("login"))
        else:
            flash("이미 사용 중인 아이디입니다.")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db.check_user(request.form["username"], request.form["password"])
        if u:
            g.s["user"] = u
            log.info("login: %s", u["username"])
            return redirect(request.args.get("next") or url_for("products"))
        log.info("login 실패: %s", request.form["username"])
        flash("아이디 또는 비밀번호가 올바르지 않습니다.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    SESSIONS.pop(g.sid, None)
    return redirect(url_for("products"))


@app.route("/products")
def products():
    recent = db.recent_orders(g.s["user"]["id"]) if g.s["user"] else []
    return render_template("products.html", products=db.list_products(), recent=recent)


@app.route("/cart")
def cart():
    items, total = cart_items()
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:pid>", methods=["POST"])
def cart_add(pid):
    p = db.get_product(pid)
    if not p or p["stock"] < 1:
        flash("품절된 상품입니다.")
        return redirect(url_for("products"))
    c = g.s["cart"]
    c[pid] = min(c.get(pid, 0) + 1, p["stock"])
    return redirect(url_for("cart"))


@app.route("/cart/update/<int:pid>", methods=["POST"])
def cart_update(pid):
    qty = int(request.form.get("qty", 0))
    if qty > 0:
        g.s["cart"][pid] = qty
    else:
        g.s["cart"].pop(pid, None)
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items, total = cart_items()
    if not items:
        return redirect(url_for("cart"))
    if request.method == "POST":
        ship = total if total >= 30000 else total + 3000
        ok, oid = db.place_order(g.s["user"]["id"], items, ship, APP_ENV)
        log.info("order #%s %s (%s) user=%s", oid, "success" if ok else "fail", APP_ENV, g.s["user"]["username"])
        if not ok:
            flash("재고가 부족해 주문에 실패했습니다.")
            g.s["cart"].clear()
            return redirect(url_for("products"))
        g.s["cart"].clear()
        return redirect(url_for("order_done", oid=oid))
    return render_template("checkout.html", items=items, total=total)


@app.route("/order/<int:oid>")
@login_required
def order_done(oid):
    o = db.get_order(oid, g.s["user"]["id"])
    if not o:
        return redirect(url_for("products"))
    return render_template("order.html", o=o)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
