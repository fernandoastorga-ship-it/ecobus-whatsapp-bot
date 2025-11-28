from flask import Flask, request, jsonify
import requests
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

print("🚀 Iniciando bot Ecobus...")

# 🔐 Autenticación con Google Sheets
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    print("📌 Cargando credenciales...")
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "/etc/secrets/credentials.json", scope
    )
    client = gspread.authorize(creds)
    print("📌 Credenciales cargadas correctamente")

    GOOGLE_SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID")
    ss = client.open_by_key(GOOGLE_SHEETS_ID)

    print("📄 Buscando hoja 'Solicitudes'...")
    sheet = ss.worksheet("Solicitudes")
    print("📄 Hoja de cálculo cargada correctamente 🟢")

except Exception as e:
    print("❌ ERROR INICIAL:", repr(e))

# 🔑 Variables de entorno para WhatsApp API
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")


# 🔎 Endpoint para verificación con Meta
@app.route("/", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("🔗 Webhook verificado correctamente")
        return challenge, 200

    print("❌ Error en verificación Webhook")
    return "Token inválido", 403


# 📥 Endpoint para mensajes entrantes
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📥 Mensaje recibido:", data)
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(port=int(os.environ["PORT"]), host="0.0.0.0")
