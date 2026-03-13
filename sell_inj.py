from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid, time, json, os, random, string, threading
import requests

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

app = Flask(__name__)
CORS(app)

# ======================
# ENV VARIABLES
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DATA_FILE = "database.json"

# Timing settings base sa HTML/Free logic mo
TOKEN_EXPIRY = 60       # seconds
KEY_EXPIRY_FREE = 43200 # 12 hours (base sa info sa HTML mo)
COOLDOWN = 10
KEY_LIMIT = 1200        # 20 mins cooldown base sa HTML mo

KEY_DURATIONS_VIP = {
    "1d": 86400, "3d": 259200, "7d": 604800, 
    "30d": 2592000, "60d": 5184000, "lifetime": None
}

# ======================
# Load/Save Database
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
    # Linisin ang mga expired tokens para hindi bumigat ang DB
    for t in list(db.get("tokens", {}).keys()):
        if now - db["tokens"][t]["time"] > TOKEN_EXPIRY:
            del db["tokens"][t]

# ======================
# API ROUTES (Para sa HTML at Injector)
# ======================

@app.route("/")
def home():
    return "KAZE SERVER ONLINE 🚀"

@app.route("/token")
def get_token():
    cleanup()
    ip = request.remote_addr
    now = time.time()
    
    # Check cooldown para sa Free Key
    if ip in db.get("cooldowns", {}) and now - db["cooldowns"][ip] < COOLDOWN:
        return f"Wait {int(COOLDOWN - (now - db['cooldowns'][ip]))}s", 429
    
    # Check kung may active key pa ang IP na to
    if ip in db.get("ip_limit", {}):
        if now - db["ip_limit"][ip] < KEY_LIMIT:
            return "Wait before getting new key", 403

    token_id = str(uuid.uuid4())
    if "tokens" not in db: db["tokens"] = {}
    db["tokens"][token_id] = {"ip": ip, "time": now}
    if "cooldowns" not in db: db["cooldowns"] = {}
    db["cooldowns"][ip] = now
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

    # Generate the key with the prefix your Injector expects
    key = "KazeFreeKey-" + ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    db["keys"][key] = {
        "expiry": now + KEY_EXPIRY_FREE,
        "device": None,
        "type": "FREE",
        "expired": False
    }
    
    if "ip_limit" not in db: db["ip_limit"] = {}
    db["ip_limit"][ip] = now
    
    del db["tokens"][token_id]
    save_db()
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

    # Device binding logic
    if data["device"] is None:
        data["device"] = device
        save_db()
        return "valid"

    if data["device"] == device:
        return "valid"

    return "locked"

# ======================
# TELEGRAM BOT LOGIC
# ======================

def genkey_telegram(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /genkey 1d")
        return
    
    duration = context.args[0]
    if duration not in KEY_DURATIONS_VIP:
        update.message.reply_text("Invalid duration")
        return

    key = "Kaze-" + ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    expiry = None
    if KEY_DURATIONS_VIP[duration]:
        expiry = time.time() + KEY_DURATIONS_VIP[duration]

    db["keys"][key] = {
        "device": None,
        "expiry": expiry,
        "type": "VIP",
        "expired": False
    }
    save_db()
    update.message.reply_text(f"✅ VIP Key: `{key}`\nDuration: {duration}", parse_mode="Markdown")

def run_bot():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("genkey", genkey_telegram))
    updater.start_polling()

# ======================
# MAIN RUN
# ======================
if __name__ == "__main__":
    # Start bot in background
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Run Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
