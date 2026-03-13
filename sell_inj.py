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
    "lifetime": None
}

# ======================
# Load database
# ======================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        db = json.load(f)
else:
    db = {"keys": {}}

def save_db():
    with open(DATA_FILE, "w") as f:
        json.dump(db, f, indent=2)

# ======================
# Helpers
# ======================
def generate_key():
    return "Kaze" + ''.join(random.choices(string.ascii_letters + string.digits, k=12))

def notify_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": message
            },
            timeout=5
        )
    except:
        pass

# ======================
# TELEGRAM COMMANDS
# ======================

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🚀 Kaze Injector Key Bot\n\n"
        "Commands:\n"
        "/genkey 1d\n"
        "/genkey 3d\n"
        "/genkey 7d\n"
        "/genkey 30d\n"
        "/genkey 60d\n"
        "/genkey lifetime\n"
        "/revoke KEY\n"
        "/list"
    )

def genkey_cmd(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /genkey 1d")
        return

    duration = context.args[0]

    if duration not in KEY_DURATIONS:
        update.message.reply_text("Invalid duration")
        return

    key = generate_key()

    expiry = None
    if KEY_DURATIONS[duration]:
        expiry = int(time.time()) + KEY_DURATIONS[duration]

    db["keys"][key] = {
        "device": None,
        "expiry": expiry,
        "duration": duration,
        "expired": False
    }

    save_db()

    update.message.reply_text(
        f"✅ Key Generated\n\n"
        f"Key: `{key}`\n"
        f"Duration: {duration}",
        parse_mode="Markdown"
    )

    notify_telegram(f"🆕 New Key Generated\nKey: {key}\nDuration: {duration}")

def revoke_cmd(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /revoke KEY")
        return

    key = context.args[0]

    if key not in db["keys"]:
        update.message.reply_text("Key not found")
        return

    db["keys"][key]["expired"] = True
    save_db()

    update.message.reply_text(f"⛔ Key revoked:\n{key}")

    notify_telegram(f"⛔ Key revoked\nKey: {key}")

def list_cmd(update: Update, context: CallbackContext):
    if not db["keys"]:
        update.message.reply_text("No keys in database")
        return

    text = "📋 Keys:\n\n"

    for k,v in db["keys"].items():
        status = "Expired" if v["expired"] else "Active"
        text += f"{k} | {v['duration']} | {status}\n"

    update.message.reply_text(text)

# ======================
# TELEGRAM BOT THREAD
# ======================

def run_bot():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("genkey", genkey_cmd))
    dp.add_handler(CommandHandler("revoke", revoke_cmd))
    dp.add_handler(CommandHandler("list", list_cmd))

    print("Telegram bot started...")
    updater.start_polling()
    updater.idle()

# ======================
# API ROUTES
# ======================

@app.route("/")
def home():
    return "Kaze Injector Server Online 🚀"

@app.route("/verify")
def verify():

    key = request.args.get("key")
    device = request.args.get("device")

    if not key or key not in db["keys"]:
        return "invalid"

    data = db["keys"][key]
    now = int(time.time())

    if data["expired"]:
        return "expired"

    if data["expiry"] and now > data["expiry"]:
        data["expired"] = True
        save_db()
        return "expired"

    # device binding
    if data["device"] is None:
        data["device"] = device
        save_db()

    if data["device"] != device:
        return "locked"

    notify_telegram(
        f"🔐 Key Login\n"
        f"Key: {key}\n"
        f"Device: {device}"
    )

    return "valid"

@app.route("/revoke")
def revoke_api():
    key = request.args.get("key")

    if key not in db["keys"]:
        return jsonify({"status":"error","message":"Key not found"})

    db["keys"][key]["expired"] = True
    save_db()

    notify_telegram(f"⛔ Key revoked via API\nKey: {key}")

    return jsonify({"status":"success"})

@app.route("/list")
def list_api():
    return jsonify(db["keys"])

# ======================
# RUN
# ======================

if __name__ == "__main__":

    # Start telegram bot in background
    threading.Thread(target=run_bot).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
