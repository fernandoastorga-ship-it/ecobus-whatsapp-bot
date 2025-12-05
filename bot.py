import os
import requests
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

# =========================
# VARIABLES DE ENTORNO
# =========================
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ecobus_token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")

# SMTP / CORREO
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER if SMTP_USER else "no-reply@ecobus.cl")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "fabian@ecobus.cl")

# =========================
# GOOGLE SHEETS
# =========================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1

# Memoria temporal de usuarios
usuarios = {}

# =========================
# UTILIDADES WHATSAPP
# =========================
def enviar_texto(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message}
    }
    r = requests.post(url, headers=headers, json=data)
    print("📤 WhatsApp texto:", r.status_code, r.text)


def enviar_botones(to, cuerpo: str, botones):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": cuerpo},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": b["id"], "title": b["title"]}
                    }
                    for b in botones
                ]
            }
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print("📤 Botones:", r.status_code, r.text)


def menu_principal(to):
    enviar_botones(
        to,
        "Hola 👋 Soy el asistente de *Ecobus* 🚍\n¿Qué quieres hacer hoy?",
        [
            {"id": "cotizar", "title": "Cotizar viaje"},
            {"id": "ejecutivo", "title": "Ejecutivo"}
        ]
    )


def enviar_confirmacion(to):
    enviar_botones(
        to,
        "¿Está todo correcto?",
        [
            {"id": "confirmar_si", "title": "Sí"},
            {"id": "confirmar_no", "title": "Corregir"}
        ]
    )

# =========================
# VALIDACIONES
# =========================
def email_valido(correo):
    return "@" in correo and "." in correo.split("@")[-1]


def hora_valida(hora):
    try:
        datetime.strptime(hora, "%H:%M")
        return True
    except Exception:
        return False

# =========================
# CORREO A EXECUTIVO
# =========================
def enviar_correo(usuario):
    try:
        cuerpo = f"""
Nueva cotización recibida 🚍

👤 Nombre: {usuario['Nombre']}
📧 Correo: {usuario['Correo']}
📅 Fecha: {usuario['Fecha Viaje']}
👥 Pasajeros: {usuario['Pasajeros']}
📍 Origen: {usuario['Origen']}
🎯 Destino: {usuario['Destino']}
🕒 Ida: {usuario['Hora Ida']}
🕒 Regreso: {usuario['Hora Regreso']}
📱 Teléfono: {usuario['Telefono']}
"""
        msg = MIMEText(cuerpo, "plain", "utf-8")
        msg["Subject"] = "Nueva solicitud de cotización - Ecobus"
        msg["From"] = FROM_EMAIL
        msg["To"] = NOTIFY_EMAIL

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, NOTIFY_EMAIL, msg.as_string())
        server.quit()
        print("📧 Email enviado correctamente")

    except Exception as e:
        print("⚠️ Error email:", e)

# =========================
# MOSTRAR RESUMEN
# =========================
def mostrar_resumen(to):
    u = usuarios[to]
    enviar_texto(
        to,
        f"🔥 *Resumen del viaje*:\n\n"
        f"👤 {u['Nombre']}\n"
        f"📧 {u['Correo']}\n"
        f"📅 {u['Fecha Viaje']}\n"
        f"👥 {u['Pasajeros']}\n"
        f"📍 {u['Origen']} → {u['Destino']}\n"
        f"🕒 {u['Hora Ida']} - {u['Hora Regreso']}\n"
        f"📱 {u['Telefono']}\n"
    )

# =========================
# FLUJO PRINCIPAL
# =========================
def procesar_flujo(to, texto):
    u = usuarios[to]

    if u["estado"] == "nombre":
        u["Nombre"] = texto
        u["estado"] = "correo"
        enviar_texto(to, "📧 ¿Cuál es tu correo de contacto?")
        return

    if u["estado"] == "correo":
        if not email_valido(texto):
            enviar_texto(to, "Correo inválido 😬\nEj: cliente@empresa.cl")
            return
        u["Correo"] = texto
        u["estado"] = "pasajeros"
        enviar_texto(to, "👥 ¿Cuántos pasajeros?")
        return

    if u["estado"] == "pasajeros":
        u["Pasajeros"] = texto
        u["estado"] = "fecha"
        enviar_texto(to, "📅 Fecha DD-MM-AAAA")
        return

    if u["estado"] == "fecha":
        try:
            fecha = datetime.strptime(texto, "%d-%m-%Y").date()
            if fecha < date.today():
                enviar_texto(to, "Debe ser una fecha futura ⏳")
                return
            u["Fecha Viaje"] = fecha.strftime("%d-%m-%Y")
            u["estado"] = "origen"
            enviar_texto(to, "📍 Dirección de origen")
        except:
            enviar_texto(to, "⚠️ Ejemplo: 25-12-2025")
        return

    if u["estado"] == "origen":
        u["Origen"] = texto
        u["estado"] = "destino"
        enviar_texto(to, "🎯 Dirección de destino")
        return

    if u["estado"] == "destino":
        u["Destino"] = texto
        u["estado"] = "ida"
        enviar_texto(to, "🕒 Hora ida (HH:MM)")
        return

    if u["estado"] == "ida":
        if not hora_valida(texto):
            enviar_texto(to, "⚠️ Ej: 08:30")
            return
        u["Hora Ida"] = texto
        u["estado"] = "regreso"
        enviar_texto(to, "🕒 Hora regreso (HH:MM)")
        return

    if u["estado"] == "regreso":
        if not hora_valida(texto):
            enviar_texto(to, "⚠️ Ej: 18:00")
            return
        u["Hora Regreso"] = texto
        u["estado"] = "telefono"
        enviar_texto(to, "📱 Teléfono de contacto")
        return

    if u["estado"] == "telefono":
        u["Telefono"] = texto
        u["estado"] = "confirmar"
        mostrar_resumen(to)
        enviar_confirmacion(to)
        return

    if u["estado"] == "confirmar":
        if texto in ["confirmar_si", "sí", "si"]:
            try:
                sheet.append_row([
                    datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    u["Nombre"], u["Correo"], u["Fecha Viaje"],
                    u["Pasajeros"], u["Origen"], u["Destino"],
                    u["Hora Ida"], u["Hora Regreso"], u["Telefono"]
                ])
                enviar_correo(u)
            except Exception as e:
                print("❌ Error Sheets:", e)

            enviar_texto(
                to,
                "🎉 *Solicitud recibida exitosamente!*\n"
                "Estamos preparando tu cotización 🚍\n"
                "📧 Revisa tu correo 📩"
            )
            usuarios.pop(to)
        else:
            enviar_texto(to, "👌 Vamos de nuevo 🚍")
            usuarios.pop(to)
            menu_principal(to)


# =========================
# WEBHOOK
# =========================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Token inválido", 403

    data = request.get_json()
    print("📩 DATA:", data)

    try:
        entry = data["entry"][0]["changes"][0]["value"]

        if "messages" not in entry:
            print("Ignorado (sin mensajes)")
            return jsonify({"status": "ok"}), 200

        for msg in entry["messages"]:
            tipo = msg.get("type")
            de = msg.get("from")

            if de not in usuarios:
                usuarios[de] = {"estado": None}

            texto = ""

            if tipo == "text":
                texto = msg["text"]["body"].strip()

            elif tipo == "interactive":
                texto = msg["interactive"]["button_reply"]["id"]

            texto_lower = texto.lower()

            if texto_lower in ["hola", "menú", "menu"]:
                usuarios[de]["estado"] = None
                return menu_principal(de)

            if usuarios[de]["estado"] is None:
                if texto == "cotizar":
                    usuarios[de] = {"estado": "nombre"}
                    enviar_texto(de, "👤 ¿Tu nombre?")
                elif texto == "ejecutivo":
                    enviar_texto(de, "📞 +56 9 9871 1060")
                else:
                    menu_principal(de)
            else:
                procesar_flujo(de, texto)

    except Exception as e:
        print("❌ ERROR WEBHOOK:", e)

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot Ecobus Activo 🚍", 200


if __name__ == "__main__":
    app.run(port=10000, debug=False)
