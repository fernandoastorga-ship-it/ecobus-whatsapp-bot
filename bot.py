import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Variables de entorno desde Render
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ecobus_token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "904716166058727")  # Confirmado
FB_API_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"


# 🌍 Ruta principal para test rápido
@app.route("/", methods=["GET"])
def home():
    return "🤖 Ecobus Bot ON!", 200


# 📩 Webhook verificación y recepción de mensajes
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Verificación inicial del webhook con Meta
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("🟢 Webhook verificado correctamente")
            return challenge, 200
        else:
            return "Token verification failed", 403

    # POST → Llegan mensajes reales de WhatsApp
    data = request.get_json()
    print("📥 Datos recibidos:", data)

    try:
        messages = data["entry"][0]["changes"][0]["value"]["messages"]
        for message in messages:
            sender = message["from"]  # número de quien envía
            if "text" in message:
                user_message = message["text"]["body"]
                print(f"📩 Mensaje de {sender}: {user_message}")
                send_whatsapp_message(sender, "Hola 👋 Soy el asistente de Ecobus 🚍 ¿En qué puedo ayudarte?")
    except Exception as e:
        print("⚠️ No hay mensajes para procesar:", e)

    return jsonify({"status": "ok"}), 200


# 💬 Función para responder mensajes
def send_whatsapp_message(to, message):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message}
    }

    response = requests.post(FB_API_URL, headers=headers, json=payload)

    print("📤 Enviando respuesta:", response.status_code, response.text)


# Ejecutar la app (para pruebas locales)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
