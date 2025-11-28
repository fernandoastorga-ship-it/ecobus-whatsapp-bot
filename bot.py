import os
import json
import requests
from datetime import datetime
from flask import Flask, request

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ==========================
# 🔐 ENV VARIABLES
# ==========================
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ecobus123")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "/etc/secrets/credentials.json")

# ==========================
# 📊 CONEXIÓN GOOGLE SHEETS
# ==========================
def connect_google_sheets():
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_PATH, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Solicitudes").sheet1
        print("🟢 Google Sheets conectado OK")
        return sheet
    except Exception as e:
        print(f"❌ Error conectando Google Sheets: {e}")
        return None

sheet = connect_google_sheets()

# ==========================
# ✉️ ENVIAR MENSAJE WHATSAPP
# ==========================
def send_whatsapp_message(to, message):
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

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
    print("📩 Respuesta Meta:", response.text)
    return response.json()

# ==========================
# 📌 WEBHOOK VERIFICACIÓN
# ==========================
@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("🟢 Webhook verificado!")
        return challenge
    return "No autorizado", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    print("📩 Webhook recibido:", request.json)
    return "OK", 200

# ==========================
# 🚀 ENDPOINT DE PRUEBA
# ==========================
@app.route("/test", methods=["GET"])
def test():
    try:
        if not sheet:
            return "Google Sheets no está disponible", 500

        # Recuperar parámetros
        nombre = request.args.get("nombre", "Sin Nombre")
        correo = request.args.get("correo", "N/A")
        pasajeros = request.args.get("pasajeros", "0")
        origen = request.args.get("origen", "N/A")
        destino = request.args.get("destino", "N/A")
        hora_ida = request.args.get("hora_ida", "N/A")
        hora_regreso = request.args.get("hora_regreso", "N/A")
        telefono = request.args.get("telefono", "56998711060") # tu número por defecto

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Guardar en Google Sheets
        sheet.append_row([
            timestamp,
            nombre,
            correo,
            pasajeros,
            origen,
            destino,
            hora_ida,
            hora_regreso,
            telefono
        ])

        print("📝 Registro guardado en Sheets con éxito")

        # Enviar confirmación al WhatsApp
        send_whatsapp_message(telefono, f"Hola {nombre}, tu solicitud fue registrada con éxito ✔️🚍")

        return "TEST OK: Dato guardado y mensaje enviado", 200

    except Exception as e:
        print("❌ Error en /test:", e)
        return f"Error: {e}", 500

@app.route("/", methods=["GET"])
def home():
    return "BOT RUNNING - ECOBUS 🚍", 200

# ==========================
# RUN
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
