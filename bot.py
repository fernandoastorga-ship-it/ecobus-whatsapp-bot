from flask import Flask, request
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

app = Flask(__name__)

# =============================
# GOOGLE SHEETS SETUP
# =============================
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    print("📄 Google Sheets conectado correctamente 🟢")
except Exception as e:
    sheet = None
    print("❌ Error conectando Google Sheets:", e)

# =============================
# WEBHOOK VERIFICATION (GET)
# =============================
@app.route("/webhook", methods=["GET"])
def verify_token():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        print("🟢 Webhook verificado correctamente")
        return challenge
    print("🔴 Error verificando Webhook")
    return "Token inválido", 403

# =============================
# RECEIVE MESSAGE (POST)
# =============================
@app.route("/webhook", methods=["POST"])
def receive_message():
    try:
        data = request.get_json()
        print("📩 Datos recibidos:", data)

        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" in value:
            message = value["messages"][0]
            sender = message["from"]
            msg_text = message.get("text", {}).get("body", "")

            print(f"📨 Mensaje de {sender}: {msg_text}")

            # Guardar en Google Sheets
            if sheet:
                sheet.append_row([sender, msg_text])
                print("📝 Mensaje guardado en Google Sheets")

            # Enviar respuesta
            send_whatsapp_message(sender, "¡Hola! Soy el bot de Ecobus 🚌✨ ¿En qué puedo ayudarte?")

        return "EVENT_RECEIVED", 200

    except Exception as e:
        print("⚠️ Error procesando mensaje:", e)
        return "EVENT_NOT_RECEIVED", 200

# =============================
# SEND WHATSAPP MESSAGE
# =============================
def send_whatsapp_message(to, message):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message}
    }

    response = requests.post(url, headers=headers, json=data)
    print("📤 Enviando respuesta:", response.status_code, response.text)
    return response

# =============================
# RUN LOCAL ONLY
# =============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
