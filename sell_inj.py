import os
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests, os, time

# ===== WEBKEEP ALIVE =====
app_web = Flask(__name__)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port)).start()

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Set your bot token
PANEL_URL = "https://codm-injector-panel.onrender.com"

def genkey(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: /genkey 1d")
        return

    duration = context.args[0]
    if duration not in ["1d","3d","7d","30d","lifetime"]:
        update.message.reply_text("Invalid duration. Use 1d,3d,7d,30d,lifetime")
        return

    # Request key from panel
    try:
        resp = requests.get(f"{PANEL_URL}/vipgen?duration={duration}", timeout=5)
        if resp.status_code == 200:
            key = resp.text.strip()
            update.message.reply_text(f"✅ VIP Key: `{key}`\nDuration: {duration}", parse_mode="Markdown")
        else:
            update.message.reply_text("Failed to generate key. Try again later.")
    except Exception as e:
        update.message.reply_text(f"Error: {e}")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("genkey", genkey))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    keep_alive()
    main()
