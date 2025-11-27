import os
import requests
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from datetime import datetime

# Cargar variables .env
load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PHONE_ID = os.getenv("PHONE_ID")
ADMIN_PHONE = os.getenv("ADMIN_PHONE")
SHEET_NAME = os.getenv("SHEET_NAME")

URL = f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages"

app = Flask(__name__)

# Google Sheets permisos
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# Memoria temporal de sesiones
sesiones = {}

# ---------------------
# FUNCIONES DE RESPUESTA
# ---------------------
def enviar_texto(numero, cuerpo):
    data = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": cuerpo}
    }
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    r = requests.post(URL, json=data, headers=headers)
    print("📩 TEXTO STATUS:", r.status_code)


def enviar_menu(numero):
    data = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "👋 Bienvenido a *Ecobus / Ecovan* 🚍\n\n¿Qué deseas hacer?"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "cotizar", "title": "📩 Cotizar"}},
                    {"type": "reply", "reply": {"id": "ejecutivo", "title": "👤 Ejecutivo"}}
                ]
            }
        }
    }
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    r = requests.post(URL, json=data, headers=headers)
    print("📋 MENÚ STATUS:", r.status_code)

# ---------------------
# GUARDAR EN GOOGLE SHEETS
# ---------------------
def guardar(cot):
    try:
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            cot.get("nombre"),
            cot.get("correo"),
            cot.get("pasajeros"),
            cot.get("origen"),
            cot.get("destino"),
            cot.get("hora_ida"),
            cot.get("hora_retorno"),
            "Pendiente",
            ""
        ])
        print("✔ Guardado en Sheets")
        return True
    except Exception as e:
        print("❌ ERROR Sheets:", e)
        return False

# ---------------------
# WEBHOOK VERIFICACIÓN
# ---------------------
@app.route("/webhook", methods=["GET"])
def verificar():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Error token"

# ---------------------
# WEBHOOK DE MENSAJES
# ---------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("\n📥 DATA:", data)

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        mensajes = entry.get("messages", [])

        if not mensajes:
            return jsonify("No message")

        mensaje = mensajes[0]
        numero = mensaje["from"]
        texto = mensaje.get("text", {}).get("body", "").lower()
        id_boton = mensaje.get("interactive", {}).get("button_reply", {}).get("id")

        if numero not in sesiones:
            sesiones[numero] = {"estado": "menu"}

        estado = sesiones[numero]["estado"]
        print("🔄 Estado:", estado)

        # Cualquier texto → mostrar menú si estamos en menu
        if estado == "menu":
            if id_boton == "cotizar" or texto == "cotizar":
                sesiones[numero] = {"estado": "nombre", "numero": numero}
                enviar_texto(numero, "📛 Nombre del solicitante:")
                return jsonify({"ok": True})

            if id_boton == "ejecutivo" or texto == "ejecutivo":
                enviar_texto(numero, "📞 Un ejecutivo te contactará pronto.")
                enviar_texto(ADMIN_PHONE, f"⚠ Cliente solicita ejecutivo: {numero}")
                return jsonify({"ok": True})

            enviar_menu(numero)
            return jsonify({"ok": True})

        if estado == "nombre":
            sesiones[numero]["nombre"] = texto
            sesiones[numero]["estado"] = "correo"
            enviar_texto(numero, "📧 Correo de contacto:")
            return jsonify({"ok": True})

        if estado == "correo":
            sesiones[numero]["correo"] = texto
            sesiones[numero]["estado"] = "origen"
            enviar_texto(numero, "📍 Dirección de origen del viaje:")
            return jsonify({"ok": True})

        if estado == "origen":
            sesiones[numero]["origen"] = texto
            sesiones[numero]["estado"] = "destino"
            enviar_texto(numero, "🏁 Dirección de destino:")
            return jsonify({"ok": True})

        if estado == "destino":
            sesiones[numero]["destino"] = texto
            sesiones[numero]["estado"] = "pasajeros"
            enviar_texto(numero, "🧍 Cantidad de pasajeros:")
            return jsonify({"ok": True})

        if estado == "pasajeros":
            sesiones[numero]["pasajeros"] = texto
            sesiones[numero]["estado"] = "ida"
            enviar_texto(numero, "🕒 Hora de salida:")
            return jsonify({"ok": True})

        if estado == "ida":
            sesiones[numero]["hora_ida"] = texto
            sesiones[numero]["estado"] = "vuelta"
            enviar_texto(numero, "⏱ Hora de retorno:")
            return jsonify({"ok": True})

        if estado == "vuelta":
            sesiones[numero]["hora_retorno"] = texto
            sesiones[numero]["estado"] = "confirmar"
            enviar_texto(numero, "¿Confirmar cotización? (SI / NO)")
            return jsonify({"ok": True})

        if estado == "confirmar":
            if texto in ["si", "sí", "yes"]:
                ok = guardar(sesiones[numero])
                if ok:
                    enviar_texto(numero, "🎯 ¡Listo! Tu solicitud fue registrada con éxito.")
                    enviar_texto(ADMIN_PHONE, f"📝 Nueva cotización: {sesiones[numero]}")
                sesiones[numero] = {"estado": "menu"}
                enviar_menu(numero)
                return jsonify({"ok": True})

            enviar_texto(numero, "Cancelada. Volviendo al menú...")
            sesiones[numero] = {"estado": "menu"}
            enviar_menu(numero)
            return jsonify({"ok": True})

    except Exception as e:
        print("💥 ERROR:", e)

    return jsonify({"status": "ok"})

# ---------------------
if __name__ == "__main__":
    app.run(port=3000, debug=True)
