import os
import json
from flask import Flask, request
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "/etc/secrets/credentials.json")
SHEET_NAME = os.getenv("SHEET_NAME", "Solicitudes Ecobus - WhatsApp Bot")

MESSAGES_API_URL = "https://graph.facebook.com/v18.0/me/messages"

# Conexión Google Sheets
def sheets_connect():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS, scope)
        client = gspread.authorize(credentials)
        sheet = client.open(SHEET_NAME).sheet1
        print("📄 Google Sheets conectado correctamente 🟢")
        return sheet
    except Exception as e:
        print(f"❌ Error conectando Sheets: {e}")
        return None

sheet = sheets_connect()

# Enviar mensaje por WhatsApp
def send_whatsapp_message(number, text):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(MESSAGES_API_URL, headers=headers, json=body)

# Webhook Verify
@app.route("/webhook", methods=["GET"])
def verify():
    challenge = request.args.get("hub.challenge")
    token = request.args.get("hub.verify_token")
    
    if token == VERIFY_TOKEN:
        print("🟢 Webhook verificado con Meta")
        return challenge
    return "Error de verificación", 403

# Recibir mensajes y responder
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 Mensaje recibido:", json.dumps(data, indent=2))

    try:
        entry = data["entry"][0]["changes"][0]["value"]["messages"][0]
        number = entry["from"]
        message = entry["text"]["body"]
        
        print(f"📬 Mensaje de {number}: {message}")

        # Guardar en Sheets
        if sheet:
            sheet.append_row([message, number])
            print("🟢 Guardado en Sheets")
        
        # Responder al usuario
        response_text = "¡Gracias por tu mensaje! Pronto te contactaremos 🚐✨"
        send_whatsapp_message(number, response_text)

    except Exception as e:
        print("⚠ No es un mensaje entrante o faltan datos:", e)

    return "EVENT_RECEIVED", 200


@app.route("/", methods=["GET"])
def home():
    return "Bot Ecobus funcionando 🚌✨"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
