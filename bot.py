from flask import Flask, request
import requests
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)

# 🌍 Variables desde Render (Environment)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_ID = os.getenv("PHONE_ID")
SHEET_NAME = os.getenv("SHEET_NAME")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "/etc/secrets/credentials.json")
print("DEBUG GOOGLE_CREDENTIALS:", GOOGLE_CREDENTIALS)
import os
print("EXISTE ARCHIVO?", os.path.exists(GOOGLE_CREDENTIALS))


# 📄 Autorización Google Sheets
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    print("📄 Hoja de cálculo cargada correctamente 🟢")
except Exception as e:
    print("❌ Error cargando Google Sheets:", e)


# 📩 Función para enviar mensaje a WhatsApp
def send_whatsapp_message(to, message):
    url = f"https://graph.facebook.com/v21.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=data)
    print("📤 Enviado a WhatsApp:", response.json())


# 🔗 Webhook entrada Meta (GET & POST)
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            print("🔐 Verificación del webhook exitosa")
            return request.args.get("hub.challenge")
        print("🚫 Error en verificación del token")
        return "Error de verificación", 403

    if request.method == "POST":
        print("📥 Mensaje recibido desde WhatsApp")
        data = request.get_json()
        print(json.dumps(data, indent=4))

        try:
            message = data["entry"][0]["changes"][0]["value"]["messages"][0]
            user_number = message["from"]

            if "text" in message:
                user_message = message["text"]["body"]
            else:
                user_message = "(sin texto)"

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Guardar en Google Sheets (solo número por ahora)
            sheet.append_row([timestamp, "", "", "", "", "", "", user_number])

            send_whatsapp_message(user_number,
                "👋 ¡Gracias por contactar con Ecobus!\n\n"
                "Hemos recibido tu mensaje y estamos procesando tu solicitud 🚍💙"
            )

        except Exception as e:
            print("⚠️ Error procesando mensaje:", e)

        return "EVENT_RECEIVED", 200


# 🏠 Página principal
@app.route("/", methods=["GET"])
def home():
    return "🚀 Bot WhatsApp Ecobus funcionando 🟢", 200


# ▶ Ejecutar servidor cuando estamos en Render
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
