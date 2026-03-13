from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid, time, json, os, random, string, threading
import requests

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

app = Flask(__name__)
CORS(app)

# ======================
# ENV VARIABLES & CONSTANTS
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DATA_FILE = "database.json"

TOKEN_EXPIRY = 60       # seconds
KEY_EXPIRY_FREE = 1800  # 30 minutes for free keys
COOLDOWN = 10
KEY_LIMIT = 600

KEY_DURATIONS_VIP = {
    "1d": 86400,
    "3d": 259200,
    "7d": 604800,
    "30d": 2592000,
    "60d": 5184000,
    "lifetime": None
}

# ======================
# Load DB (Isang DB lang para sa lahat)
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

def cleanup():
    now = time.time()
    # Remove expired tokens
    if "tokens" in db:
        for t in list(db["tokens"].keys()):
            if now - db["tokens"][t]["time"] > TOKEN_EXPIRY:
                del db["tokens"][t]
    # Remove expired IP limits
    if "ip_limit" in db:
        for ip in list(db["ip_limit"].keys()):
            if now - db["ip_limit"][ip] > KEY_LIMIT:
                del db["ip_limit"][ip]

# ======================
# HELPERS
# ======================
def notify_telegram(message):
    if not BOT_TOKEN or not CHAT_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": message}, timeout=5)
    except: pass

# ======================
# TELEGRAM COMMANDS (VIP)
# ======================
def genkey_cmd(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /genkey 1d")
        return
    duration = context.args[0]
    if duration not in KEY_DURATIONS_VIP:
        update.message.reply_text("Invalid duration")
        return
    
    # VIP Key Prefix
    key = "Kaze-" + ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    expiry = None
    if KEY_DURATIONS_VIP[duration]:
        expiry = int(time.time()) + KEY_DURATIONS_VIP[duration]

    db["keys"][key] = {"device": None, "expiry": expiry, "duration": duration, "expired": False}
    save_db()
    update.message.reply_text(f"✅ VIP Key Generated\nKey: `{key}`", parse_mode="Markdown")

# (Dagdagan mo na lang ng /start, /list, /revoke commands mo dito...)

# ======================
# API ROUTES (FREE KEY SYSTEM)
# ======================
@app.route("/")
def home(): return "KAZE SERVER ONLINE 🚀"

@app.route("/token")
def token():
    cleanup()
    ip = request.remote_addr
    now = time.time()
    if ip in db.get("cooldowns", {}) and now - db["cooldowns"][ip] < COOLDOWN:
        return f"Wait {int(COOLDOWN - (now - db['cooldowns'][ip]))}s", 429
    if ip in db.get("ip_limit", {}):
        return "Wait before getting new key", 403

    token_id = str(uuid.uuid4())
    if "tokens" not in db: db["tokens"] = {}
    db["tokens"][token_id] = {"ip": ip, "time": now}
    if "cooldowns" not in db: db["cooldowns"] = {}
    db["cooldowns"][ip] = now
    save_db()
    return token_id

@app.route("/getkey")
def getkey():
    cleanup()
    token_id = request.args.get("token")
    if not token_id or token_id not in db.get("tokens", {}):
        return jsonify({"status": "error", "message": "Invalid token"}), 403

    # Free Key Prefix
    key = "KazeFreeKey-" + ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    db["keys"][key] = {
        "expiry": time.time() + KEY_EXPIRY_FREE,
        "device": None,
        "duration": "30m (Free)",
        "expired": False
    }
    if "ip_limit" not in db: db["ip_limit"] = {}
    db["ip_limit"][request.remote_addr] = time.time()
    del db["tokens"][token_id]
    save_db()
    return jsonify({"status": "success", "key": key})

# ======================
# UNIVERSAL VERIFY (VIP & FREE)
# ======================
@app.route("/verify")
def verify():
    cleanup()
    key = request.args.get("key")
    device = request.args.get("device")
    if not key or key not in db["keys"]: return "invalid"

    data = db["keys"][key]
    now = time.time()

    if data.get("expired"): return "expired"
    if data.get("expiry") and now > data["expiry"]:
        data["expired"] = True
        save_db()
        return "expired"

    if data["device"] is None:
        data["device"] = device
        save_db()
        return "valid"
    
    return "valid" if data["device"] == device else "locked"

# ======================
# RUN
# ======================
def run_bot():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("genkey", genkey_cmd))
    # ... add other handlers here ...
    updater.start_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
