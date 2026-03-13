from flask import Flask, request
import os, time, json, random, string, threading, requests

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

DATA_FILE = "database.json"

KEY_DURATIONS = {
    "1d": 86400,
    "7d": 604800,
    "30d": 2592000,
    "60d": 5184000,
    "lifetime": None
}

# =====================
# LOAD DATABASE
# =====================

if os.path.exists(DATA_FILE):
    with open(DATA_FILE,"r") as f:
        db = json.load(f)
else:
    db = {"keys":{}}

def save_db():
    with open(DATA_FILE,"w") as f:
        json.dump(db,f,indent=2)

# =====================
# GENERATE KEY
# =====================

def generate_key():
    return "Kaze-" + ''.join(random.choices(string.ascii_letters+string.digits,k=12))

# =====================
# VERIFY API (FOR INJECTOR)
# =====================

@app.route("/verify")
def verify():

    key = request.args.get("key")
    device = request.args.get("device")

    if key not in db["keys"]:
        return "invalid"

    data = db["keys"][key]

    now = time.time()

    if data["expired"]:
        return "expired"

    if data["expiry"] and now > data["expiry"]:
        data["expired"] = True
        save_db()
        return "expired"

    if data["device"] is None:
        data["device"] = device
        save_db()
        return "valid"

    if data["device"] == device:
        return "valid"

    return "locked"

# =====================
# TELEGRAM BOT POLLING
# =====================

def bot_loop():

    offset = None

    while True:

        try:

            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"timeout":100,"offset":offset},
                timeout=120
            )

            data = r.json()

            for update in data["result"]:

                offset = update["update_id"] + 1

                if "message" not in update:
                    continue

                msg = update["message"]

                chat_id = msg["chat"]["id"]

                text = msg.get("text","")

                if text.startswith("/genkey"):

                    parts = text.split()

                    if len(parts) < 2:
                        send(chat_id,"Usage:\n/genkey 1d")
                        continue

                    duration = parts[1]

                    if duration not in KEY_DURATIONS:
                        send(chat_id,"Invalid duration")
                        continue

                    key = generate_key()

                    expiry = None

                    if KEY_DURATIONS[duration]:
                        expiry = time.time() + KEY_DURATIONS[duration]

                    db["keys"][key] = {
                        "device":None,
                        "expiry":expiry,
                        "expired":False
                    }

                    save_db()

                    send(chat_id,f"✅ Key Generated\n\n{key}\nDuration: {duration}")

                elif text.startswith("/revoke"):

                    parts = text.split()

                    if len(parts) < 2:
                        send(chat_id,"Usage:\n/revoke KEY")
                        continue

                    key = parts[1]

                    if key not in db["keys"]:
                        send(chat_id,"Key not found")
                        continue

                    db["keys"][key]["expired"] = True
                    save_db()

                    send(chat_id,"Key revoked")

        except:
            time.sleep(5)

# =====================
# TELEGRAM SEND
# =====================

def send(chat_id,msg):

    try:
        requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            params={
                "chat_id":chat_id,
                "text":msg
            }
        )
    except:
        pass

# =====================
# MAIN
# =====================

if __name__ == "__main__":

    threading.Thread(target=bot_loop).start()

    port = int(os.environ.get("PORT",10000))

    app.run(host="0.0.0.0",port=port)
