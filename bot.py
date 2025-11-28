from flask import Flask, request, jsonify
import requests
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

print("🚀 Iniciando bot Ecobus...")

try:
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    print("📌 Cargando credenciales...")
    creds = ServiceAccountCredentials.from_json_keyfile_name("/etc/secrets/credentials.json", scope)
    client = gspread.authorize(creds)
    print("📌 Credenciales cargadas correctamente")

    GOOGLE_SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID")
    print(f"📌 Sheets ID: {GOOGLE_SHEETS_ID}")
    
    sheet = client.open_by_key(GOOGLE_SHEETS_ID).worksheet("Solicitudes")
    print("📄 Hoja de cálculo cargada correctamente 🟢")

except Exception as e:
    print("❌ ERROR INICIAL:", e)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")

user_states = {}

@app.route("/", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        print("🔗 Webhook verificado correctamente")
        return request.args.get("hub.challenge")
    return "❌ Token inválido", 403

@app.route("/", methods=["POST"])
def webhook():
    print("📥 Mensaje entrante recibido")
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(port=int(os.environ["PORT"]), host="0.0.0.0")
