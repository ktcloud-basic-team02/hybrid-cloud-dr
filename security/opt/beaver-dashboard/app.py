import os, time, socket, platform, subprocess
import psutil, pymysql
from flask import Flask, jsonify, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=None)

# (표시 이름, systemd 유닛)
SERVICES = [
    ("kubelet",    "snap.kubelet-eks.daemon.service"),
    ("containerd", "containerd.service"),
    ("docker",     "docker.service"),
    ("tailscaled", "tailscaled.service"),
    ("ssh",        "ssh.socket"),
    ("chrony",     "chrony.service"),
    ("ssm-agent",  "snap.amazon-ssm-agent.amazon-ssm-agent.service"),
    ("대시보드",    "beaver-dashboard.service"),
]
psutil.cpu_percent(percpu=True)


def os_name():
    try:
        return platform.freedesktop_os_release()["PRETTY_NAME"]
    except Exception:
        return platform.platform()


def sh(*args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        return ""


def service_status(unit):
    try:
        if sh("systemctl", "show", "-p", "LoadState", "--value", unit) in ("not-found", ""):
            return "missing"
        st = sh("systemctl", "is-active", unit)
        return st if st in ("active", "failed") else "inactive"
    except Exception:
        return "missing"


def mysql_stats():
    host = os.environ.get("DB_HOST")
    if not host:
        return {"ok": False}
    try:
        c = pymysql.connect(host=host, user=os.environ["DB_USER"],
                            password=os.environ["DB_PASSWORD"],
                            connect_timeout=2, read_timeout=2)
        with c.cursor() as cur:
            cur.execute("SHOW GLOBAL STATUS WHERE Variable_name IN "
                        "('Uptime','Threads_connected','Threads_running',"
                        "'Slow_queries','Aborted_connects','Questions')")
            st = {k: int(v) for k, v in cur.fetchall()}
            cur.execute("SELECT VERSION(), @@max_connections")
            ver, maxc = cur.fetchone()
        c.close()
        return {"ok": True, "version": ver, "max_connections": int(maxc),
                "uptime": st["Uptime"], "threads_connected": st["Threads_connected"],
                "threads_running": st["Threads_running"], "slow_queries": st["Slow_queries"],
                "aborted_connects": st["Aborted_connects"], "questions": st["Questions"]}
    except Exception:
        return {"ok": False}


def top_procs():
    procs = []
    for p in psutil.process_iter(["pid", "name", "username", "cpu_percent",
                                  "memory_percent", "memory_info", "cmdline"]):
        i = p.info
        if not i["memory_info"]:
            continue
        procs.append({"pid": i["pid"], "user": i["username"] or "-",
                      "cpu": i["cpu_percent"] or 0.0, "mem": i["memory_percent"] or 0.0,
                      "rss": i["memory_info"].rss, "name": i["name"] or "-",
                      "cmd": " ".join(i["cmdline"] or []) or i["name"] or "-"})
    by_cpu = sorted(procs, key=lambda x: x["cpu"], reverse=True)[:15]
    by_mem = sorted(procs, key=lambda x: x["mem"], reverse=True)[:15]
    merged = {p["pid"]: p for p in by_cpu + by_mem}
    return list(merged.values()), len(procs)


@app.route("/")
def index():
    return send_from_directory(os.path.join(BASE, "static"), "index.html")


@app.route("/api/stats")
def stats():
    cores = psutil.cpu_percent(percpu=True)
    vm, sw, du, nio = psutil.virtual_memory(), psutil.swap_memory(), psutil.disk_usage("/"), psutil.net_io_counters()
    top, count = top_procs()
    return jsonify({
        "hostname": socket.gethostname(), "os": os_name(),
        "kernel": platform.release(),
        "tz": time.strftime("%Z"),
        "ts_ip": sh("tailscale", "ip", "-4").split("\n")[0],
        "time": time.time(), "boot_time": psutil.boot_time(),
        "cpu_percent": sum(cores) / len(cores), "cpu_count": len(cores), "cpu_per_core": cores,
        "mem": {"percent": vm.percent, "used": vm.used, "total": vm.total},
        "swap": {"used": sw.used, "total": sw.total},
        "disk": {"percent": du.percent, "used": du.used, "total": du.total},
        "load": list(os.getloadavg()), "process_count": count,
        "net": {"recv": nio.bytes_recv, "sent": nio.bytes_sent},
        "services": [{"name": n, "status": service_status(u)} for n, u in SERVICES],
        "mysql": mysql_stats(),
        "users": [{"name": u.name, "terminal": u.terminal, "host": u.host, "started": u.started}
                  for u in psutil.users()],
        "top": top,
    })