from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid, time, json, os, random, string, threading
import requests

app = Flask(__name__)
CORS(app)

# ======================
# ENV VARIABLES
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DATA_FILE = "database.json"

# Timing settings
TOKEN_EXPIRY = 60         # seconds
KEY_EXPIRY_FREE = 43200   # 12 hours for free keys
COOLDOWN = 10
KEY_LIMIT = 1200

KEY_DURATIONS_VIP = {
    "1d": 86400, "3d": 259200, "7d": 604800,
    "30d": 2592000, "60d": 5184000, "lifetime": None
}

# ======================
# Load/Save DB
# ======================
def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"keys": {}, "tokens": {}, "ip_limit": {}, "cooldowns": {}}

db = load_db()

def save_db():
    with open(DATA_FILE, "w") as f:
        json.dump(db, f, indent=2)

def cleanup():
    now = time.time()
    for t in list(db.get("tokens", {}).keys()):
        if now - db["tokens"][t]["time"] > TOKEN_EXPIRY:
            del db["tokens"][t]
    # mark expired keys
    for k, v in db.get("keys", {}).items():
        if v.get("expiry") and now > v["expiry"]:
            v["expired"] = True

# ======================
# Telegram notify helper
# ======================
def notify_telegram(message):
    def _send():
        try:
            requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"},
                timeout=5
            )
        except:
            pass
    threading.Thread(target=_send).start()

# ======================
# Flask API
# ======================
@app.route("/")
def home():
    return "KAZE SERVER ONLINE 🚀"

@app.route("/token")
def get_token():
    cleanup()
    ip = request.remote_addr
    now = time.time()
    if ip in db.get("cooldowns", {}) and now - db["cooldowns"][ip] < COOLDOWN:
        return f"Wait {int(COOLDOWN - (now - db['cooldowns'][ip]))}s", 429
    if ip in db.get("ip_limit", {}) and now - db["ip_limit"][ip] < KEY_LIMIT:
        return "Wait before getting new key", 403
    token_id = str(uuid.uuid4())
    db.setdefault("tokens", {})[token_id] = {"ip": ip, "time": now}
    db.setdefault("cooldowns", {})[ip] = now
    save_db()
    return token_id

@app.route("/getkey")
def get_key_api():
    cleanup()
    token_id = request.args.get("token")
    ip = request.remote_addr
    now = time.time()
    if not token_id or token_id not in db.get("tokens", {}):
        return jsonify({"status": "error", "message": "Invalid token"}), 403
    key = "KazeFreeKey-" + ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    db["keys"][key] = {
        "expiry": now + KEY_EXPIRY_FREE,
        "device": None,
        "type": "FREE",
        "expired": False
    }
    db.setdefault("ip_limit", {})[ip] = now
    del db["tokens"][token_id]
    save_db()
    notify_telegram(f"🆕 New free key generated:\n`{key}`\nExpires in 12h")
    return jsonify({"status": "success", "key": key})

@app.route("/verify")
def verify():
    key = request.args.get("key")
    device = request.args.get("device")
    if not key or key not in db["keys"]:
        return "invalid"
    data = db["keys"][key]
    now = time.time()
    if data.get("expired"):
        return "expired"
    if data.get("expiry") and now > data["expiry"]:
        data["expired"] = True
        save_db()
        return "expired"
    if data["device"] is None:
        data["device"] = device
        save_db()
        remaining = int(data["expiry"] - now) if data["expiry"] else None
        notify_telegram(f"🔐 Key used\nKey: `{key}`\nDevice: `{device}`\nRemaining: {remaining}s")
        return "valid"
    if data["device"] == device:
        remaining = int(data["expiry"] - now) if data["expiry"] else None
        notify_telegram(f"🔐 Key used\nKey: `{key}`\nDevice: `{device}`\nRemaining: {remaining}s")
        return "valid"
    return "locked"

@app.route("/genkey")
def genkey_api():
    cleanup()
    duration = request.args.get("duration")
    if duration not in KEY_DURATIONS_VIP:
        return jsonify({"status": "error", "message": "Invalid duration"}), 400
    key = "Kaze-" + ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    expiry = None
    if KEY_DURATIONS_VIP[duration]:
        expiry = time.time() + KEY_DURATIONS_VIP[duration]
    db["keys"][key] = {"device": None, "expiry": expiry, "type": "VIP", "expired": False, "duration": duration}
    save_db()
    notify_telegram(f"🆕 VIP Key generated\nKey: `{key}`\nDuration: {duration}")
    return jsonify({"status": "success", "key": key, "duration": duration})

@app.route("/revoke")
def revoke():
    key = request.args.get("key")
    if not key or key not in db["keys"]:
        return jsonify({"status": "error", "message": "Key not found"}), 404
    db["keys"][key]["expired"] = True
    save_db()
    notify_telegram(f"⛔ Key revoked: `{key}`")
    return jsonify({"status": "success","message":"Key revoked"})

# ======================
# Run Flask only
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
