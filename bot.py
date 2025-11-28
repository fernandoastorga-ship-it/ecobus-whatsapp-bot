import os
import json
import requests
from flask import Flask, request
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "botardo")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_PATH = "/etc/secrets/credentials.json"  # Render Secrets

# ========================
# 📌 Conexión Google Sheets
# ========================
def get_google_sheet():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=scopes)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sheet.worksheet("Solicitudes")  # NOMBRE EXACTO DE TU PESTAÑA ⚠
        return worksheet

    except Exception as e:
        print(f"❌ Error cargando Google Sheets: {e}")
        return None

# ========================
# 📌 Enviar mensaje WhatsApp
# ========================
def send_message(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
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
    
    res = requests.post(url, headers=headers, json=data)
    print("📤 RESPUESTA WHATSAPP:", res.status_code, res.text)
    return res

# ========================
# 📌 Webhook Verificación
# ========================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Token inválido"

# ========================
# 📌 Webhook Mensajes entrantes
# ========================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 DATA RECIBIDA:", data)

    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        user = msg["from"]
        text = msg["text"]["body"]

        sheet = get_google_sheet()

        if sheet:
            sheet.append_row(["Mensaje", user, text])
            send_message(user, f"📌 Recibido: {text}")
        else:
            send_message(user, "⚠ Error con el sistema, inténtalo más tarde.")

    except Exception as e:
        print("⚠ Error procesando mensaje:", e)

    return "EVENT_RECEIVED"

@app.route("/", methods=["GET"])
def home():
    return "Servidor de Ecobus Bot funcionando 🚐"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
