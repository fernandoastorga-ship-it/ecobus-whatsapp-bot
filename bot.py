from flask import Flask, request, jsonify
import requests
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
SHEET_NAME = os.getenv("SHEET_NAME")

# --- GOOGLE SHEETS ---
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        os.getenv("GOOGLE_CREDENTIALS"),
        ["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    print("📄 Google Sheet cargada correctamente")
except Exception as e:
    print(f"❌ Error cargando Google Sheets: {e}")

# --- VERIFICAR WEBHOOK ---
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("🟢 Webhook verificado!")
        return challenge, 200
    return "Error de verificación", 403

# --- RECIBIR MENSAJES ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 Recibido:", data)

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        message = changes["value"]["messages"][0]

        phone = message["from"]
        msg_text = message["text"]["body"]

        print(f"📲 Mensaje de {phone}: {msg_text}")

        responder_whatsapp(phone, "Gracias! Tu mensaje fue recibido 👍")

        # Guardamos en la Sheet
        sheet.append_row(["", phone, msg_text])

    except:
        print("⚠️ Evento recibido sin mensaje... ignorado")

    return jsonify({"status": "ok"}), 200


# --- RESPONDER ---
def responder_whatsapp(to, text):
    url = f"https://graph.facebook.com/v20.0/{os.getenv('PHONE_ID')}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": text}
    }

    r = requests.post(url, headers=headers, json=body)
    print("📤 Enviado:", r.text)


@app.route("/", methods=["GET"])
def home():
    return "🚀 Bot Ecobus Activo", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
