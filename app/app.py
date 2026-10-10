from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify, flash
import db
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "hybrid-cloud-dr-secret")
SERVER_ENV = os.environ.get("SERVER_ENV", "onprem")


@app.context_processor
def inject_globals():
    cart_count = 0
    if "user_id" in session:
        items, _ = db.get_cart(session["user_id"])
        cart_count = sum(i["qty"] for i in items)

    user = None
    if "user_id" in session:
        user = {"id": session["user_id"], "username": session.get("username")}

    return {
        "env": SERVER_ENV,
        "env_label": SERVER_ENV.upper(),
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
        username = request.form.get("username")
        password = request.form.get("password")
        user = db.check_user(username, password)
        if user:
            session["user_id"] = user["USER_ID"]
            session["username"] = user["EMAIL"]
            return redirect(url_for("products"))
        return render_template("login.html", error="아이디 또는 비밀번호가 올바르지 않습니다.")
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
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
    items, total = db.get_cart(session["user_id"])
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:pid>", methods=["POST"])
def cart_add(pid):
    ajax = request.headers.get("X-Requested-With") == "fetch"
    if "user_id" not in session:
        if ajax:
            return jsonify({"login": url_for("login")}), 401
        return redirect(url_for("login"))
    db.add_to_cart(session["user_id"], pid, 1)
    if ajax:
        items, _ = db.get_cart(session["user_id"])
        return jsonify({"count": sum(i["qty"] for i in items)})
    return redirect(url_for("products"))


@app.route("/cart/update/<int:pid>", methods=["POST"])
def cart_update(pid):
    if "user_id" not in session:
        return redirect(url_for("login"))
    qty = int(request.form.get("qty", 0))
    db.update_cart(session["user_id"], pid, qty)
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if "user_id" not in session:
        return redirect(url_for("login"))
    items, total = db.get_cart(session["user_id"])
    if not items:
        return redirect(url_for("cart"))
    if request.method == "POST":
        order_id, err = db.place_order(session["user_id"], SERVER_ENV)
        if order_id:
            return redirect(url_for("order_complete", oid=order_id))
        flash(f"주문에 실패했어요. {err}")
        return redirect(url_for("cart"))
    return render_template("checkout.html", items=items, total=total)


@app.route("/order/<int:oid>")
def order_complete(oid):
    if "user_id" not in session:
        return redirect(url_for("login"))
    o = db.get_order(oid)
    return render_template("order.html", o=o)


@app.route("/api/reset", methods=["POST"])
def api_reset():
    success = db.reset_db()
    if success:
        return jsonify({"status": "success", "message": "Database reset successfully."})
    return jsonify({"status": "fail", "message": "Reset failed."}), 500


@app.route("/health")
def health():
    return {"env": SERVER_ENV, "status": "ok"}


@app.route("/metrics")
def metrics():
    counts = db.order_counts()
    lines = [f'shop_orders_total{{env="{r["env"]}",status="{r["status"]}"}} {r["n"]}' for r in counts]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
