from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid, time, json, os, random, string, threading
import requests

app = Flask(__name__)
CORS(app)

# ======================
# Constants
# ======================
DATA_FILE = "database.json"
KEY_DURATIONS = {
    "1d": 86400,
    "3d": 259200,
    "7d": 604800,
    "30d": 2592000,
    "60d": 5184000,
    "lifetime": 315360000  # 10 years
}
TOKEN_EXPIRY = 60
KEY_LIMIT = 600  # prevent key spam per IP
COOLDOWN = 10

# Telegram
BOT_TOKEN = "8666247437:AAFIqrWLLbH-0z8W4CnX6nRHjojKX_B6YG8"
CHAT_ID = "7201369115"

# ======================
# Load DB
# ======================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        db = json.load(f)
else:
    db = {
        "keys": {},
        "tokens": {},
        "ip_limit": {},
        "cooldowns": {}
    }

def save_db():
    with open(DATA_FILE, "w") as f:
        json.dump(db, f, indent=2)

# ======================
# Helper Functions
# ======================
def cleanup():
    now = time.time()
    # Remove expired tokens
    for t in list(db["tokens"].keys()):
        if now - db["tokens"][t]["time"] > TOKEN_EXPIRY:
            del db["tokens"][t]
    # Remove expired keys
    for k, v in list(db["keys"].items()):
        if v["expiry"] and now > v["expiry"]:
            db["keys"][k]["expired"] = True
    # Remove IP limits
    for ip in list(db["ip_limit"].keys()):
        if now - db["ip_limit"][ip] > KEY_LIMIT:
            del db["ip_limit"][ip]

def generate_key():
    return "Kaze" + ''.join(random.choices(string.ascii_letters + string.digits, k=12))

def notify_telegram(message):
    def _send():
        try:
            requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params={"chat_id": CHAT_ID, "text": message, "parse_mode":"Markdown"},
                timeout=5
            )
        except:
            pass
    threading.Thread(target=_send).start()

# ======================
# Routes
# ======================
@app.route("/")
def home():
    return "SELL INJECTOR SERVER ONLINE 🚀"

# ======= Generate key via token =======
@app.route("/genkey")
def genkey():
    cleanup()
    token = request.args.get("token")
    duration = request.args.get("duration", "1d")
    ip = request.remote_addr
    now = time.time()

    if not token or token not in db["tokens"]:
        return jsonify({"status":"error","message":"Invalid token"}),403

    data = db["tokens"][token]
    if data["ip"] != ip:
        return jsonify({"status":"error","message":"IP mismatch"}),403

    if now - data["time"] > TOKEN_EXPIRY:
        del db["tokens"][token]
        save_db()
        return jsonify({"status":"error","message":"Token expired"}),403

    # cooldown per IP
    if ip in db["ip_limit"]:
        return jsonify({"status":"error","message":"Wait before generating another key"}),403

    if duration not in KEY_DURATIONS:
        return jsonify({"status":"error","message":"Invalid duration"}),400

    key = generate_key()
    db["keys"][key] = {
        "device": None,
        "expiry": now + KEY_DURATIONS[duration] if duration != "lifetime" else None,
        "duration": duration,
        "expired": False
    }

    db["ip_limit"][ip] = now
    del db["tokens"][token]
    save_db()

    notify_telegram(f"🆕 New key generated!\nKey: {key}\nDuration: {duration}")

    return jsonify({"status":"success","key": key, "duration": duration})

# ======= Verify key =======
@app.route("/verify")
def verify():
    cleanup()
    key = request.args.get("key")
    device = request.args.get("device")
    now = time.time()

    if not key or key not in db["keys"]:
        return "invalid"

    data = db["keys"][key]

    # Check expiration
    if data.get("expired"):
        return "expired"
    if data["expiry"] and now > data["expiry"]:
        data["expired"] = True
        save_db()
        return "expired"

    # Bind device
    if data["device"] is None:
        data["device"] = device
        save_db()
        remaining = int(data["expiry"] - now) if data["expiry"] else None
        notify_telegram(f"🔐 Key used\nKey: {key}\nDevice: {device}\nRemaining: {remaining}s")
        return "valid"

    if data["device"] == device:
        remaining = int(data["expiry"] - now) if data["expiry"] else None
        notify_telegram(f"🔐 Key used\nKey: {key}\nDevice: {device}\nRemaining: {remaining}s")
        return "valid"

    return "locked"

# ======= Token generation for API =======
@app.route("/token")
def token():
    cleanup()
    ip = request.remote_addr
    now = time.time()

    if ip in db["cooldowns"] and now - db["cooldowns"][ip] < COOLDOWN:
        wait = int(COOLDOWN - (now - db["cooldowns"][ip]))
        return f"Cooldown active wait {wait}s",429

    token_id = str(uuid.uuid4())
    db["tokens"][token_id] = {"ip": ip, "time": now}
    db["cooldowns"][ip] = now
    save_db()
    return token_id

# ======= Admin: Revoke key =======
@app.route("/revoke")
def revoke():
    key = request.args.get("key")
    if not key or key not in db["keys"]:
        return jsonify({"status":"error","message":"Key not found"}),404
    db["keys"][key]["expired"] = True
    save_db()
    notify_telegram(f"⛔ Key revoked: {key}")
    return jsonify({"status":"success","message":"Key revoked"})

# ======= List keys =======
@app.route("/list")
def list_keys():
    return jsonify(db["keys"])

# ======================
# RUN
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port)
