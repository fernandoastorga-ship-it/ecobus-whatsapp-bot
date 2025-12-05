import os
import requests
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

app = Flask(__name__)

# Variables de entorno
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ecobus_token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL")

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1

# Memoria temporal
usuarios = {}

# Enviar mensaje por WhatsApp
def enviar(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to, "text": {"body": message}}
    r = requests.post(url, headers=headers, json=data)
    print("📤 Texto de WhatsApp:", r.status_code, r.text)


# ============================
# CORREO DE COTIZACIÓN
# ============================
def enviar_correo_notificacion(usuario):
    try:
        import smtplib
        from email.mime.text import MIMEText

        cuerpo = (
            "📬 Nueva solicitud de cotización:\n\n"
            f"👤 Nombre: {usuario['Nombre']}\n"
            f"📧 Correo: {usuario['Correo']}\n"
            f"📅 Fecha: {usuario['Fecha']}\n"
            f"👥 Pasajeros: {usuario['Pasajeros']}\n"
            f"📍 Origen: {usuario['Origen']}\n"
            f"🎯 Destino: {usuario['Destino']}\n"
            f"🕒 Ida: {usuario['Hora Ida']}\n"
            f"🕒 Regreso: {usuario['Hora Regreso']}\n"
            f"📱 Teléfono: {usuario['Telefono']}\n"
        )

        msg = MIMEText(cuerpo, "plain", "utf-8")
        msg["Subject"] = "Nueva solicitud de cotización - Ecobus"
        msg["From"] = FROM_EMAIL
        msg["To"] = NOTIFY_EMAIL

        print("📬 Intentando enviar correo...")

        server = smtplib.SMTP(SMTP_HOST, int(SMTP_PORT))
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, NOTIFY_EMAIL, msg.as_string())
        server.quit()

        print("📧 Correo enviado correctamente a", NOTIFY_EMAIL)
    except Exception as e:
        print("⚠️ Error enviando correo:", str(e))


# ============================
# FLUJO DE COTIZACIÓN
# ============================

def menu_principal(to):
    enviar(to,
        "Hola 👋 Soy el asistente de Ecobus 🚍\n"
        "¿Qué quieres hacer?\n\n"
        "1️⃣ Cotizar un viaje\n"
        "2️⃣ Hablar con un ejecutivo 👨‍💼"
    )


def procesar_flujo(to, texto):
    usuario = usuarios[to]

    if usuario["estado"] == "nombre":
        usuario["Nombre"] = texto
        usuario["estado"] = "correo"
        enviar(to, "📧 ¿Cuál es tu correo de contacto?")

    elif usuario["estado"] == "correo":
        usuario["Correo"] = texto
        usuario["estado"] = "fecha"
        enviar(to, "📅 ¿Qué día necesitas el viaje? (Ej: 25-12-2024)")

    elif usuario["estado"] == "fecha":
        usuario["Fecha"] = texto
        usuario["estado"] = "pasajeros"
        enviar(to, "👥 ¿Cuántos pasajeros serán?")

    elif usuario["estado"] == "pasajeros":
        usuario["Pasajeros"] = texto
        usuario["estado"] = "origen"
        enviar(to, "📍 ¿Desde dónde salen? (Dirección exacta)")

    elif usuario["estado"] == "origen":
        usuario["Origen"] = texto
        usuario["estado"] = "destino"
        enviar(to, "📍 ¿Hacia dónde se dirigen?")

    elif usuario["estado"] == "destino":
        usuario["Destino"] = texto
        usuario["estado"] = "hora_ida"
        enviar(to, "🕒 ¿A qué hora es la ida? (Ej: 07:30)")

    elif usuario["estado"] == "hora_ida":
        usuario["Hora Ida"] = texto
        usuario["estado"] = "hora_vuelta"
        enviar(to, "🕒 ¿Hora de regreso? (Ej: 18:00)")

    elif usuario["estado"] == "hora_vuelta":
        usuario["Hora Regreso"] = texto
        usuario["estado"] = "telefono"
        enviar(to, "📱 Confírmame tu número telefónico de contacto")

    elif usuario["estado"] == "telefono":
        usuario["Telefono"] = texto
        usuario["estado"] = "confirmar"

        resumen = (
            "Perfecto 😄 Este es el resumen del viaje:\n\n"
            f"👤 {usuario['Nombre']}\n"
            f"📧 {usuario['Correo']}\n"
            f"📅 {usuario['Fecha']}\n"
            f"👥 {usuario['Pasajeros']}\n"
            f"📍 {usuario['Origen']} → {usuario['Destino']}\n"
            f"🕒 Ida: {usuario['Hora Ida']} | Regreso: {usuario['Hora Regreso']}\n"
            f"📱 {usuario['Telefono']}\n\n"
            "¿Está todo correcto? (Sí/No)"
        )
        enviar(to, resumen)

    elif usuario["estado"] == "confirmar":
        if texto.lower() in ["si", "sí", "correcto"]:

            enviar_correo_notificacion(usuario)

            enviar(to,
                "🎉 *¡Solicitud recibida exitosamente!*\n"
                "Estamos preparando tu cotización 🚍\n"
                "📧 Revisa tu correo, ahí te llegará toda la info.\n"
                "Un ejecutivo te contactará pronto 🙌"
            )

            usuarios.pop(to)
        else:
            enviar(to, "👌 No hay problema, vamos nuevamente 🚍")
            usuarios.pop(to)
            menu_principal(to)


# ============================
# WEBHOOK
# ============================

@app.route("/", methods=["GET"])
def home():
    return "🤖 Ecobus Bot Operativo", 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    data = request.get_json()
    print("📩 DATOS:", data)

    try:
        mensajes = data["entry"][0]["changes"][0]["value"].get("messages", [])
        if not mensajes:
            print("📥 Evento sin 'mensajes', ignorado.")
            return "ok", 200

        for m in mensajes:
            texto = m["text"]["body"].strip().lower() if "text" in m else ""
            to = m["from"]

            if to not in usuarios:
                usuarios[to] = {"estado": None}

            if texto in ["hola", "menu", "buenas"]:
                usuarios[to]["estado"] = None
                menu_principal(to)
                return "ok", 200

            if usuarios[to]["estado"] is None:
                if texto == "1":
                    usuarios[to]["estado"] = "nombre"
                    enviar(to, "Perfecto! 😊 Empecemos.\n👤 ¿Cuál es tu nombre?")
                elif texto == "2":
                    enviar(to, "📞 Un ejecutivo está disponible aquí:\n+56 9 9871 1060")
                else:
                    menu_principal(to)
            else:
                procesar_flujo(to, texto)

    except Exception as e:
        print("❌ ERROR WEBHOOK:", str(e))

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(port=10000, debug=False)
