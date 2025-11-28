from flask import Flask, request, jsonify
import requests
import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Google Sheets auth
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ["GOOGLE_SHEETS_ID"]).worksheet("Solicitudes")

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")

user_states = {}

def refresh_whatsapp_token():
    global WHATSAPP_TOKEN
    WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")

def send_message(phone, text):
    refresh_whatsapp_token()
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=data)

def send_buttons(phone, body, buttons):
    refresh_whatsapp_token()
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": buttons}
        }
    }
    requests.post(url, headers=headers, json=data)

@app.route("/", methods=["GET"])
def verify():
    if (request.args.get("hub.mode") == "subscribe" and
        request.args.get("hub.verify_token") == VERIFY_TOKEN):
        return request.args.get("hub.challenge"), 200
    return "Unauthorized", 403

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    try:
        phone = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]

        if phone not in user_states:
            user_states[phone] = {"step": 1}
            send_message(phone, "👋 ¡Hola! Soy el asistente de Ecobus 🚌✨\n\n¿Cuál es tu nombre?")
            return jsonify({"status": "ok"})

        state = user_states[phone]

        if state["step"] == 1:
            state["nombre"] = message["text"]["body"]
            state["step"] = 2
            send_message(phone, "Perfecto 👍\nAhora, ¿cuál es tu correo?")

        elif state["step"] == 2:
            state["correo"] = message["text"]["body"]
            state["step"] = 3
            send_buttons(phone, "¿Cuántos pasajeros necesitan viajar?", [
                {"type": "reply", "reply": {"id": "1-10", "title": "1-10"}},
                {"type": "reply", "reply": {"id": "11-20", "title": "11-20"}},
                {"type": "reply", "reply": {"id": "21-30", "title": "21-30"}},
                {"type": "reply", "reply": {"id": "30+", "title": "30+"}}
            ])

        elif state["step"] == 3:
            state["pasajeros"] = message.get("interactive", {}).get("button_reply", {}).get("title", message["text"]["body"])
            state["step"] = 4
            send_message(phone, "📍 ¿Desde dónde necesitan el servicio? (Origen)")

        elif state["step"] == 4:
            state["origen"] = message["text"]["body"]
            state["step"] = 5
            send_message(phone, "📍 ¿Hacia dónde se dirigen? (Destino)")

        elif state["step"] == 5:
            state["destino"] = message["text"]["body"]
            state["step"] = 6
            send_buttons(phone, "⏱️ Selecciona la hora de ida", [
                {"type": "reply", "reply": {"id": "07:00", "title": "07:00"}},
                {"type": "reply", "reply": {"id": "08:00", "title": "08:00"}},
                {"type": "reply", "reply": {"id": "otra", "title": "Otra"}}
            ])

        elif state["step"] == 6:
            if "interactive" in message:
                state["hora_ida"] = message["interactive"]["button_reply"]["title"]
            else:
                state["hora_ida"] = message["text"]["body"]
            state["step"] = 7
            send_buttons(phone, "⏱️ Selecciona la hora de regreso", [
                {"type": "reply", "reply": {"id": "17:00", "title": "17:00"}},
                {"type": "reply", "reply": {"id": "18:00", "title": "18:00"}},
                {"type": "reply", "reply": {"id": "otra", "title": "Otra"}}
            ])

        elif state["step"] == 7:
            if "interactive" in message:
                state["hora_vuelta"] = message["interactive"]["button_reply"]["title"]
            else:
                state["hora_vuelta"] = message["text"]["body"]

            sheet.append_row([
                str(datetime.datetime.now()),
                state["nombre"],
                state["correo"],
                state["pasajeros"],
                state["origen"],
                state["destino"],
                state["hora_ida"],
                state["hora_vuelta"],
                phone
            ])

            send_message(phone,
                "🎉 ¡Gracias! Tu solicitud fue registrada exitosamente.\n\n"
                "📌 Muy pronto un ejecutivo de Ecobus se comunicará contigo.\n\n"
                "Si necesitas algo más, solo escríbeme 😊"
            )

            user_states.pop(phone)

    except Exception as e:
        print("⚠️ Error:", e)

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(port=int(os.environ["PORT"]), host="0.0.0.0")
