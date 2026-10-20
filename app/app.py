from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify, flash, abort
import db
import hmac
import os
import socket
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

app = Flask(__name__)
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY 환경변수가 설정되지 않았습니다.")
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # HTTPS 앞단(ALB/Ingress TLS)을 붙인 뒤에만 true로 켬
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
)
SERVER_ENV = os.environ.get("SERVER_ENV", "aws").strip().lower()
if SERVER_ENV not in {"aws", "onprem"}:
    raise ValueError("SERVER_ENV must be aws or onprem")

# 쿠버네티스에서는 hostname이 곧 파드 이름
POD_NAME = os.environ.get("POD_NAME") or socket.gethostname()
NODE_NAME = os.environ.get("NODE_NAME", "")
# 파드 이름은 쿠버네티스(또는 POD_NAME 지정)일 때만 화면에 표시
SHOW_POD = bool(os.environ.get("POD_NAME") or os.environ.get("KUBERNETES_SERVICE_HOST"))

RESET_ENABLED = os.environ.get("ENABLE_RESET", "false").lower() == "true"
RESET_TOKEN = os.environ.get("RESET_TOKEN", "")
if RESET_ENABLED and not RESET_TOKEN:
    raise RuntimeError("ENABLE_RESET=true 이면 RESET_TOKEN 환경변수도 필요합니다.")

SERVICE_MODE = os.environ.get("SERVICE_MODE", "standby").strip().lower()
if SERVICE_MODE not in {"active", "standby"}:
    raise ValueError("SERVICE_MODE must be active or standby")


@app.before_request
def block_standby_writes():
    if SERVICE_MODE == "standby" and request.method not in {"GET", "HEAD", "OPTIONS"}:
        return jsonify({
            "env": SERVER_ENV,
            "mode": SERVICE_MODE,
            "message": "대기 중인 서버에서는 변경 요청을 처리할 수 없습니다."
        }), 503



@app.context_processor
def inject_globals():
    cart_count = sum(session.get("cart", {}).values())

    user = None
    if "user_id" in session:
        user = {"id": session["user_id"], "username": session.get("username")}

    return {
        "env": SERVER_ENV,
        "env_label": SERVER_ENV.upper(),
        "pod": POD_NAME,
        "pod_short": POD_NAME.split("-")[-1] if SHOW_POD else "",
        "node": NODE_NAME,
        "user": user,
        "cart_count": cart_count,
    }


@app.template_filter("won")
def format_won(value):
    try:
        return f"{int(value):,}원"
    except (ValueError, TypeError):
        return f"{value}원"


@app.route("/")
def index():
    return redirect(url_for("products"))


@app.route("/products")
def products():
    prod_list = db.list_products()
    recent = db.recent_orders(session.get("user_id")) if "user_id" in session else []
    return render_template("products.html", products=prod_list, recent=recent)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = db.check_user(username, password) if username and password else None
        if user:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("products"))
        return render_template("login.html", error="아이디 또는 비밀번호가 올바르지 않습니다.")
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            return render_template("signup.html", error="아이디와 비밀번호를 입력해 주세요.")
        success = db.create_user(username, password)
        if success:
            return redirect(url_for("login"))
        return render_template("signup.html", error="이미 존재하는 아이디입니다.")
    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("products"))


@app.route("/cart")
def cart():
    if "user_id" not in session:
        return redirect(url_for("login"))
    items, total = db.cart_items(session.get("cart", {}))
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:pid>", methods=["POST"])
def cart_add(pid):
    ajax = request.headers.get("X-Requested-With") == "fetch"
    if "user_id" not in session:
        if ajax:
            return jsonify({"login": url_for("login")}), 401
        return redirect(url_for("login"))
    cart = dict(session.get("cart", {}))
    cart[str(pid)] = cart.get(str(pid), 0) + 1
    session["cart"] = cart
    if ajax:
        return jsonify({"count": sum(cart.values())})
    return redirect(url_for("products"))


@app.route("/cart/update/<int:pid>", methods=["POST"])
def cart_update(pid):
    if "user_id" not in session:
        return redirect(url_for("login"))
    try:
        qty = int(request.form.get("qty", 0))
    except ValueError:
        return redirect(url_for("cart"))
    cart = dict(session.get("cart", {}))
    if qty <= 0:
        cart.pop(str(pid), None)
    else:
        cart[str(pid)] = qty
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if "user_id" not in session:
        return redirect(url_for("login"))
    items, total = db.cart_items(session.get("cart", {}))
    if not items:
        return redirect(url_for("cart"))
    if request.method == "POST":
        order_id, err = db.place_order(session["user_id"], session.get("cart", {}), SERVER_ENV)
        if order_id:
            session.pop("cart", None)
            return redirect(url_for("order_complete", oid=order_id))
        flash(f"주문에 실패했어요. {err}")
        return redirect(url_for("cart"))
    return render_template("checkout.html", items=items, total=total)


@app.route("/order/<int:oid>")
def order_complete(oid):
    if "user_id" not in session:
        return redirect(url_for("login"))
    # 본인 주문만 조회됨. 없는 주문과 남의 주문을 똑같이 404로 처리해 존재 여부가 드러나지 않게 함
    o = db.get_order(oid, session["user_id"])
    if o is None:
        logging.warning("order not found or not owned oid=%s user=%s", oid, session["user_id"])
        abort(404)
    return render_template("order.html", o=o)


@app.route("/api/reset", methods=["POST"])
def api_reset():
    if not RESET_ENABLED:
        return jsonify({"status": "fail", "message": "Reset is disabled."}), 403
    token = request.headers.get("X-Reset-Token", "")
    if not hmac.compare_digest(token, RESET_TOKEN):
        logging.warning("reset rejected: invalid token")
        return jsonify({"status": "fail", "message": "Forbidden."}), 403
    success = db.reset_db()
    if success:
        return jsonify({"status": "success", "message": "Database reset successfully."})
    return jsonify({"status": "fail", "message": "Reset failed."}), 500


@app.route("/live")
def live():
    return {"env": SERVER_ENV, "pod": POD_NAME, "status": "alive"}


@app.route("/health")
def health():
    if SERVICE_MODE == "standby":
        return {"env": SERVER_ENV, "mode": SERVICE_MODE, "status": "standby"}, 503
    try:
        db.ping()
    except Exception as e:
        logging.warning("health check: DB ping failed (%s)", e)
        return {"env": SERVER_ENV, "mode": SERVICE_MODE, "status": "down"}, 503
    return {"env": SERVER_ENV, "pod": POD_NAME, "mode": SERVICE_MODE, "status": "ok"}


@app.route("/metrics")
def metrics():
    counts = {(e, s): 0 for e in ("aws", "onprem") for s in ("success", "fail")}
    for r in db.order_counts():
        counts[(r["env"], r["status"])] = r["n"]
    lines = [f'shop_orders_total{{env="{e}",status="{s}"}} {n}' for (e, s), n in counts.items()]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
