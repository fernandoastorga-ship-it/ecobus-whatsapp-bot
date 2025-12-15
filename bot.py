import os
import requests
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import re
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ecobus_token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "fabian@ecobus.cl")

# GOOGLE SHEETS
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1

usuarios = {}

# -------- Validaciones --------
def email_valido(c):
    return "@" in c and "." in c.split("@")[-1]

def hora_valida(h):
    try:
        datetime.strptime(h, "%H:%M")
        return True
    except:
        return False

def telefono_valido(t):
    t = t.replace(" ", "")
    return bool(re.match(r"^\+?56?9\d{8}$", t))

# -------- WhatsApp --------
def enviar_texto(to, msg):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}",
               "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to, "text": {"body": msg}}
    requests.post(url, headers=headers, json=data)

def enviar_botones(to, cuerpo, botones):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}",
               "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": cuerpo},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in botones
                ]
            }
        }
    }
    requests.post(url, headers=headers, json=data)

# -------- Email --------
def enviar_correo(usuario):
    try:
        cuerpo = (
            f"Nueva solicitud 🚍\n\n"
            f"Nombre: {usuario['Nombre']}\n"
            f"Correo: {usuario['Correo']}\n"
            f"Fecha: {usuario['Fecha Viaje']}\n"
            f"Pasajeros: {usuario['Pasajeros']}\n"
            f"Origen: {usuario['Origen']}\n"
            f"Destino: {usuario['Destino']}\n"
            f"Ida: {usuario['Hora Ida']}\n"
            f"Regreso: {usuario['Hora Regreso']}\n"
            f"Teléfono: {usuario['Telefono']}\n"
        )

        msg = MIMEText(cuerpo, "plain", "utf-8")
        msg["Subject"] = "Nueva cotización - Ecobus"
        msg["From"] = FROM_EMAIL
        msg["To"] = NOTIFY_EMAIL

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, NOTIFY_EMAIL, msg.as_string())
        server.quit()
        print("📧 Enviado correctamente")
    except Exception as e:
        print("❌ Error al enviar correo:", e)

# -------- MENÚ --------
def menu_principal(to):
    enviar_botones(to, "¡Hola! soy el bot de Ecobus. Cuentame, ¿Qué deseas hacer hoy? 🚍",
                   [{"id": "cotizar", "title": "Cotizar"},
                    {"id": "ejecutivo", "title": "Ejecutivo"}])

def enviar_confirmacion(to):
    enviar_botones(
        to,
        "¿Está todo correcto?",
        [{"id": "confirmar_si", "title": "Sí"},
         {"id": "confirmar_no", "title": "Corregir"}]
    )

def mostrar_resumen(to):
    u = usuarios[to]
    resumen = (
        f"Resumen del viaje:\n\n"
        f"👤 {u['Nombre']}\n"
        f"📧 {u['Correo']}\n"
        f"📅 {u['Fecha Viaje']}\n"
        f"👥 {u['Pasajeros']}\n"
        f"📍 {u['Origen']} → {u['Destino']}\n"
        f"🕒 {u['Hora Ida']} - {u['Hora Regreso']}\n"
        f"📱 {u['Telefono']}\n\n"
        "Si quieres cambiar algo, escribe por ejemplo: *cambiar correo*"
    )
    enviar_texto(to, resumen)

# -------- Corrección dinámica --------
def corregir_campos(to, texto_lower):
    m = usuarios[to]
    mapping = {
        "nombre": "nombre",
        "correo": "correo",
        "fecha": "fecha",
        "origen": "origen",
        "destino": "destino",
        "pasajeros": "pasajeros",
        "teléfono": "telefono",
        "telefono": "telefono",
        "ida": "ida",
        "regreso": "regreso",
    }
    for key, estado in mapping.items():
        if f"cambiar {key}" in texto_lower:
            usuarios[to]["estado"] = estado
            enviar_texto(to, f"Ok! Envíame el nuevo {key}:")
            return True
    return False

# -------- Flujo principal --------
def procesar_flujo(to, texto, texto_lower):
    u = usuarios[to]

    if corregir_campos(to, texto_lower):
        return

    estado = u["estado"]

    if estado == "nombre":
        u["Nombre"] = texto
        u["estado"] = "correo"
        return enviar_texto(to, "📧 Correo?")

    if estado == "correo":
        if not email_valido(texto):
            return enviar_texto(to, "Correo inválido ⚠️")
        u["Correo"] = texto
        u["estado"] = "pasajeros"
        return enviar_texto(to, "👥 Pasajeros?")

    if estado == "pasajeros":
        u["Pasajeros"] = texto
        u["estado"] = "fecha"
        return enviar_texto(to, "📅 Fecha DD-MM-AAAA")

    if estado == "fecha":
        try:
            f = datetime.strptime(texto, "%d-%m-%Y").date()
            if f < date.today():
                return enviar_texto(to, "Fecha futura por favor ⏳")
            u["Fecha Viaje"] = f.strftime("%d-%m-%Y")
            u["estado"] = "origen"
            return enviar_texto(to, "📍 Origen?")
        except:
            return enviar_texto(to, "Formato inválido 25-12-2026")

    if estado == "origen":
        u["Origen"] = texto
        u["estado"] = "destino"
        return enviar_texto(to, "🎯 Destino?")

    if estado == "destino":
        u["Destino"] = texto
        u["estado"] = "ida"
        return enviar_texto(to, "🕒 Hora ida (HH:MM)?")

    if estado == "ida":
        if not hora_valida(texto):
            return enviar_texto(to, "Ej: 08:30 ⏱️")
        u["Hora Ida"] = texto
        u["estado"] = "regreso"
        return enviar_texto(to, "🕒 Hora regreso?")

    if estado == "regreso":
        if not hora_valida(texto):
            return enviar_texto(to, "Ej: 18:00 ⏱️")
        u["Hora Regreso"] = texto
        u["estado"] = "telefono"
        return enviar_texto(to, "📱 Teléfono?")

    if estado == "telefono":
        if not telefono_valido(texto):
            return enviar_texto(to, "Número inválido ⚠️ Ej: +56912345678")
        u["Telefono"] = texto
        u["estado"] = "confirmar"
        mostrar_resumen(to)
        return enviar_confirmacion(to)

    if estado == "confirmar":
        if texto_lower == "confirmar_si":
            sheet.append_row([
                datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                u["Nombre"], u["Correo"], u["Pasajeros"],
                u["Origen"], u["Destino"],
                u["Hora Ida"], u["Hora Regreso"],
                u["Telefono"], u["Fecha Viaje"]
            ])
            enviar_correo(u)
            enviar_texto(to,
                "🎉 ¡Solicitud confirmada!\n"
                "Estamos creando tu cotización 🚍\n"
                "📧 Revisa tu correo ✉️\n"
                "¡Gracias por preferir Ecobus! 💙"
            )
            usuarios.pop(to, None)
            return
        else:
            return enviar_texto(to, "Para corregir, escribe por ej: *cambiar correo*")

# -------- Webhook --------
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Error Token", 403

    data = request.get_json()
    entry = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})

    mensajes = entry.get("messages", [])
    for m in mensajes:
        wa_id = m.get("from")
        tipo = m.get("type", "")
        texto = ""

        if tipo == "text":
            texto = m["text"]["body"]
        elif tipo == "interactive":
            texto = m["interactive"]["button_reply"]["id"]

        texto_lower = texto.lower()

        if wa_id not in usuarios:
            usuarios[wa_id] = {"estado": None}

        if texto_lower in ["hola", "menú", "menu", "inicio"]:
            usuarios[wa_id]["estado"] = None
            menu_principal(wa_id)
            continue

        if usuarios[wa_id]["estado"] is None:
            if texto_lower == "cotizar":
                usuarios[wa_id]["estado"] = "nombre"
                enviar_texto(wa_id, "👤 Nombre?")
            elif texto_lower == "ejecutivo":
                enviar_texto(wa_id, "📞 +56 9 9871 1060")
            else:
                menu_principal(wa_id)
        else:
            procesar_flujo(wa_id, texto, texto_lower)

    return jsonify({"status": "ok"}), 200


@app.route("/")
def home():
    return "🤖 Bot Ecobus Activo", 200
