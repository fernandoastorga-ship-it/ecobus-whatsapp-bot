import os
import json
import requests
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# =================================================================
# 🔐 VARIABLES DE ENTORNO (CONFIGURAR EN RENDER)
# =================================================================
VERIFY_TOKEN = "botardo" 
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1EeYjWMYqkkXOgWQA3nElm2IQ6kWGsaSSlo3Do_j6GNc")
SHEET_NAME = "Solicitudes"

# =================================================================
# GOOGLE SHEETS
# =================================================================
def init_gsheet():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "/etc/secrets/credentials.json",
            ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        print("📄 Google Sheets conectado correctamente 🟢")
        return sheet
    except Exception as e:
        print("❌ ERROR cargando Google Sheets:", e)
        return None


sheet = init_gsheet()

# =================================================================
# 🔄 ENVIAR MENSAJES A WHATSAPP
# =================================================================
def send_message(text, to):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=payload)
    print(f"📩 Mensaje enviado → {response.text}")

# =================================================================
# 🔍 VERIFICACIÓN WEBHOOK (GET)
# =================================================================
@app.get("/webhook")
def verify_webhook():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge
    return "Token inválido", 403

# =================================================================
# 📥 PROCESAR MENSAJES (POST)
# =================================================================
@app.post("/webhook")
def webhook():
    global sheet

    data = request.get_json()
    print("📬 Webhook recibido:", json.dumps(data, indent=2, ensure_ascii=False))

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages", [])

        if messages:
            msg = messages[0]
            user_id = msg["from"]
            text = msg["text"]["body"].strip()

            # Guardar directamente lo que envía por ahora
            if sheet:
                sheet.append_row([text])
                print("Excel actualizado!")

            send_message(f"📌 Recibido: {text}", user_id)

    except Exception as e:
        print("❌ Error procesando mensaje:", e)

    return jsonify({"status": "ok"}), 200

# =================================================================
# 🚀 INICIO DEL SERVIDOR
# =================================================================
if __name__ == "__main__":
    print("🚀 Bot Ecobus ejecutándose...")
    app.run(host="0.0.0.0", port=10000)
