import os
import requests
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# ======================
# CONFIG
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
PANEL_URL = "https://codm-injector-panel.onrender.com"

# ======================
# KEEP ALIVE SERVER
# ======================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot running!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()

# ======================
# OWNER CHECK
# ======================
def is_owner(update: Update):
    return update.effective_user.id == OWNER_ID

# ======================
# START COMMAND
# ======================
def start(update: Update, context: CallbackContext):

    if not is_owner(update):
        update.message.reply_text(
        "🚫 This is private key generator panel only\n\nOwner: @KAZEHAYAMODZ")
        return

    name = update.effective_user.first_name

    text = f"""
👋 HELLO, {name}!

🔰 KAZE CODM INJECTOR
OFFICIAL VIP ACCESS PANEL

Welcome back to the official
Kaze Injector key generation system.

From this panel you can generate
your exclusive VIP License Key
to activate the injector and unlock
all premium features.

⚡ Instant Key Generation
🔐 Secure License System
🚀 Fast & Smooth Activation
🛡 Protected Access

Owner: @KAZEHAYAMODZ

Please choose an option below to continue.
"""

    keyboard = [
        [InlineKeyboardButton("🔑 Generate VIP Key", callback_data="vip")],
        [InlineKeyboardButton("⏱ Generate Hours Key", callback_data="hours")],
        [InlineKeyboardButton("📊 Panel Stats", callback_data="stats")]
    ]

    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================
# BUTTON HANDLER
# ======================
def button(update: Update, context: CallbackContext):

    query = update.callback_query
    query.answer()

    if query.from_user.id != OWNER_ID:
        query.edit_message_text("🚫 Access denied")
        return

    data = query.data

# ======================
# VIP MENU
# ======================

    if data == "vip":

        keyboard = [
            [InlineKeyboardButton("1 Day", callback_data="gen_1d")],
            [InlineKeyboardButton("3 Days", callback_data="gen_3d")],
            [InlineKeyboardButton("7 Days", callback_data="gen_7d")],
            [InlineKeyboardButton("30 Days", callback_data="gen_30d")],
            [InlineKeyboardButton("60 Days", callback_data="gen_60d")],
            [InlineKeyboardButton("Lifetime", callback_data="gen_lifetime")]
        ]

        query.edit_message_text(
            "🔑 Select VIP Key Duration",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ======================
# HOURS MENU
# ======================

    elif data == "hours":

        keyboard = []

        for i in range(1, 11):
            keyboard.append(
                [InlineKeyboardButton(f"{i} Minute", callback_data=f"gen_{i}m")]
            )

        for i in range(1, 25):
            keyboard.append(
                [InlineKeyboardButton(f"{i} Hour", callback_data=f"gen_{i}h")]
            )

        query.edit_message_text(
            "⏱ Select Duration",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ======================
# PANEL STATS
# ======================

    elif data == "stats":

        try:

            r = requests.get(f"{PANEL_URL}/stats", timeout=15)
            data = r.json()

            msg = f"""
📊 PANEL STATISTICS

Total Keys: {data['total_keys']}
Active Keys: {data['active_keys']}
Expired Keys: {data['expired_keys']}
"""

            query.edit_message_text(msg)

        except:
            query.edit_message_text("❌ Failed to get stats")

# ======================
# GENERATE KEY
# ======================

    elif data.startswith("gen_"):

        duration = data.replace("gen_", "")

        try:

            # get token
            token = requests.get(f"{PANEL_URL}/token", timeout=15).text.strip()

            # generate key
            r = requests.get(f"{PANEL_URL}/getkey?token={token}", timeout=15)

            if r.status_code != 200:
                query.edit_message_text("❌ Key generation failed")
                return

            key_data = r.json()
            key = key_data.get("key", "ERROR")

            msg = f"""
🔑 𝗞𝗘𝗬 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘𝗗
━━━━━━━━━━━━━━━━━━━━
🔑 KEY: `{key}`
⏳ EXPIRATION: {duration}
🚫 DEVICE AVAILABLE: 1 Device
📊 STATUS: SAFE
🔰 CODM INJECTOR V2

📝 Tap to copy your key
Duration will start when license login.

📲 Feedback: @KAZEHAYAMODZ
🫶 THANK YOU FOR TRUSTING
"""

            query.edit_message_text(msg, parse_mode="Markdown")

        except Exception as e:

            query.edit_message_text(f"❌ Error: {e}")

# ======================
# REVOKE COMMAND
# ======================

def revoke(update: Update, context: CallbackContext):

    if not is_owner(update):
        return

    if not context.args:
        update.message.reply_text("Usage:\n/revoke KEY")
        return

    key = context.args[0]

    try:

        r = requests.get(f"{PANEL_URL}/revoke?key={key}", timeout=15)

        if r.status_code == 200:

            update.message.reply_text(f"""
🚫 KEY REVOKED

KEY: `{key}`
STATUS: DISABLED
""", parse_mode="Markdown")

        else:
            update.message.reply_text("❌ Failed to revoke key")

    except Exception as e:

        update.message.reply_text(f"❌ Error: {e}")

# ======================
# LIST KEYS
# ======================

def listkeys(update: Update, context: CallbackContext):

    if not is_owner(update):
        return

    try:

        r = requests.get(f"{PANEL_URL}/list", timeout=15)
        data = r.json()

        if not data:
            update.message.reply_text("No active keys.")
            return

        msg = "🔑 ACTIVE KEYS\n\n"

        for k in data[:20]:
            msg += f"{k['key']} | Device:{k['device']}\n"

        update.message.reply_text(msg)

    except:

        update.message.reply_text("❌ Failed to fetch keys")

# ======================
# STATS COMMAND
# ======================

def stats(update: Update, context: CallbackContext):

    if not is_owner(update):
        return

    try:

        r = requests.get(f"{PANEL_URL}/stats", timeout=15)
        data = r.json()

        msg = f"""
📊 PANEL STATS

Total Keys: {data['total_keys']}
Active Keys: {data['active_keys']}
Expired Keys: {data['expired_keys']}
"""

        update.message.reply_text(msg)

    except:

        update.message.reply_text("❌ Failed to get stats")

# ======================
# MAIN
# ======================

def main():

    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("revoke", revoke))
    dp.add_handler(CommandHandler("list", listkeys))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()

# ======================
# RUN
# ======================

if __name__ == "__main__":
    keep_alive()
    main()
