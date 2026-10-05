import os
import json
import time
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

SEED = [
    (1, "Beaver", "Ambre Solaire", "Amber · Vanilla · Sandalwood", 50, 128000, 0, "img/p1.jpg", "50% 62%"),
    (2, "Prada", "Paradoxe", "Neroli · Pink Pear · Amber", 50, 156000, 0, "img/p2.jpg", "50% 60%"),
    (3, "Morra", "1st Collection", "Rose · Cedar · Clove · Tonka", 50, 98000, 0, "img/p3.jpg", "50% 50%"),
    (4, "Chanel", "Coco Mademoiselle Intense", "Orange · Rose · Patchouli", 50, 198000, 0, "img/p5.jpg", "50% 50%"),
    (5, "Clive Christian", "Town & Country", "Frankincense · Amber · Spice", 50, 420000, 1, "img/p6.jpg", "55% 50%"),
    (6, "Nishane", "Ani", "Vanilla · Ginger · Cardamom", 50, 215000, 0, "img/p7.jpg", "45% 50%"),
]

DDL = [
    """CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS products (
        id INT PRIMARY KEY,
        brand VARCHAR(60), name VARCHAR(100), notes VARCHAR(200),
        size_ml INT, price INT, stock INT NOT NULL,
        limited TINYINT(1) DEFAULT 0,
        image_url VARCHAR(300), pos VARCHAR(30))""",
    """CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT, items TEXT, total INT,
        status VARCHAR(10), env VARCHAR(10),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX (user_id))""",
]


def conn():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "shop"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "shop"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=3,
    )


def query(sql, args=(), one=False):
    c = conn()
    try:
        with c.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone() if one else cur.fetchall()
    finally:
        c.close()


def init_db(retries=30):
    for _ in range(retries):
        try:
            c = conn()
            break
        except pymysql.err.OperationalError:
            time.sleep(2)
    else:
        raise RuntimeError("DB 연결 실패")
    with c.cursor() as cur:
        for ddl in DDL:
            cur.execute(ddl)
        cur.execute("SELECT COUNT(*) AS n FROM products")
        if cur.fetchone()["n"] == 0:
            for r in SEED:
                cur.execute(
                    "INSERT INTO products (id,brand,name,notes,size_ml,price,stock,limited,image_url,pos) "
                    "VALUES (%s,%s,%s,%s,%s,%s,IF(%s=1,1,30),%s,%s,%s)",
                    (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[6], r[7], r[8]),
                )
    c.commit()
    c.close()


def list_products():
    return query("SELECT * FROM products ORDER BY id")


def get_product(pid):
    return query("SELECT * FROM products WHERE id=%s", (pid,), one=True)


def create_user(username, password):
    try:
        query_commit("INSERT INTO users (username,password_hash) VALUES (%s,%s)",
                     (username, generate_password_hash(password)))
        return True
    except pymysql.err.IntegrityError:
        return False


def query_commit(sql, args=()):
    c = conn()
    try:
        with c.cursor() as cur:
            cur.execute(sql, args)
            last = cur.lastrowid
        c.commit()
        return last
    finally:
        c.close()


def check_user(username, password):
    u = query("SELECT id, username, password_hash FROM users WHERE username=%s", (username,), one=True)
    if u and check_password_hash(u["password_hash"], password):
        return {"id": u["id"], "username": u["username"]}
    return None


def place_order(user_id, items, total, env):
    lines = [dict(id=i["product"]["id"], brand=i["product"]["brand"], name=i["product"]["name"],
                  qty=i["qty"], price=i["product"]["price"]) for i in items]
    c = conn()
    try:
        with c.cursor() as cur:
            ok = True
            for l in lines:
                cur.execute("UPDATE products SET stock=stock-%s WHERE id=%s AND stock>=%s",
                            (l["qty"], l["id"], l["qty"]))
                if cur.rowcount == 0:
                    ok = False
                    break
            if not ok:
                c.rollback()
            cur.execute("INSERT INTO orders (user_id,items,total,status,env) VALUES (%s,%s,%s,%s,%s)",
                        (user_id, json.dumps(lines, ensure_ascii=False), total,
                         "success" if ok else "fail", env))
            oid = cur.lastrowid
        c.commit()
        return ok, oid
    finally:
        c.close()


def _parse(o):
    o["items"] = json.loads(o["items"])
    return o


def recent_orders(user_id, n=5):
    rows = query("SELECT * FROM orders WHERE user_id=%s ORDER BY id DESC LIMIT %s", (user_id, n))
    return [_parse(r) for r in rows]


def get_order(oid, user_id):
    o = query("SELECT * FROM orders WHERE id=%s AND user_id=%s", (oid, user_id), one=True)
    return _parse(o) if o else None


def order_counts():
    return query("SELECT env, status, COUNT(*) AS n FROM orders GROUP BY env, status")


def ping():
    try:
        query("SELECT 1")
        return True
    except Exception:
        return False


def reset():
    c = conn()
    try:
        with c.cursor() as cur:
            cur.execute("TRUNCATE TABLE orders")
            cur.execute("UPDATE products SET stock=IF(limited=1,1,30)")
        c.commit()
    finally:
        c.close()
