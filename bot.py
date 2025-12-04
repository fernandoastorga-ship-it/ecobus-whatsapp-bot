import os
import requests
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import smtplib
from email.message import EmailMessage

app = Flask(__name__)

# Variables de entorno
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ecobus_token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")

# Configuración correo (para notificar cotización)
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER if SMTP_USER else "no-reply@ecobus.cl")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "fabian@ecobus.cl")

# Conexión Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key(GOOGLE_SHEETS_ID).sheet1

# Memoria de usuarios en conversación (simple diccionario en RAM)
usuarios = {}


# ----------------- UTILIDADES -----------------

def enviar_texto(to, message: str):
    """Enviar mensaje de texto normal a WhatsApp."""
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
    response = requests.post(url, headers=headers, json=data)
    print("📤 WhatsApp (texto):", response.status_code, response.text)


def enviar_interactivo_botones(to, cuerpo: str, botones):
    """
    Enviar mensaje interactivo con botones.
    botones: lista de dicts: [{"id": "cotizar", "title": "Cotizar un viaje"}, ...]
    """
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
                    } for b in botones
                ]
            }
        }
    }
    response = requests.post(url, headers=headers, json=data)
    print("📤 WhatsApp (botones):", response.status_code, response.text)


def enviar_menu_principal(to):
    """Menú principal con botones interactivos."""
    texto = "Hola 👋 Soy el asistente de *Ecobus* 🚍\n¿Qué quieres hacer hoy?"
    botones = [
        {"id": "cotizar", "title": "Cotizar un viaje"},
        {"id": "ejecutivo", "title": "Hablar con un ejecutivo"}
    ]
    enviar_interactivo_botones(to, texto, botones)


def enviar_confirmacion(to):
    """Botones de confirmación Sí / No."""
    botones = [
        {"id": "confirmar_si", "title": "Sí ✅"},
        {"id": "confirmar_no", "title": "No, corregir ❌"}
    ]
    enviar_interactivo_botones(to, "¿Está todo correcto?", botones)


def enviar_email_cotizacion(u):
    """Envía un correo con los datos de la cotización al ejecutivo."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and NOTIFY_EMAIL):
        print("⚠️ SMTP no configurado, no se envía correo.")
        return

    cuerpo = (
        "Nueva cotización Ecobus 🚍\n\n"
        f"Nombre: {u['Nombre']}\n"
        f"Correo: {u['Correo']}\n"
        f"Pasajeros: {u['Pasajeros']}\n"
        f"Fecha viaje: {u['Fecha Viaje']}\n"
        f"Origen: {u['Origen']}\n"
        f"Destino: {u['Destino']}\n"
        f"Hora ida: {u['Hora Ida']}\n"
        f"Hora regreso: {u['Hora Regreso']}\n"
        f"Teléfono: {u['Telefono']}\n"
        f"Fecha de solicitud: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n"
    )

    msg = EmailMessage()
    msg["Subject"] = "Nueva cotización Ecobus"
    msg["From"] = FROM_EMAIL
    msg["To"] = NOTIFY_EMAIL
    msg.set_content(cuerpo)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print("📧 Correo de cotización enviado a", NOTIFY_EMAIL)
    except Exception as e:
        print("❌ Error enviando correo:", e)


def mostrar_resumen(to):
    u = usuarios[to]
    resumen = (
        "🔥 *Resumen del viaje solicitado*:\n\n"
        f"👤 Nombre: {u['Nombre']}\n"
        f"📧 Correo: {u['Correo']}\n"
        f"👥 Pasajeros: {u['Pasajeros']}\n"
        f"📅 Fecha del viaje: {u['Fecha Viaje']}\n"
        f"📍 Origen: {u['Origen']}\n"
        f"🎯 Destino: {u['Destino']}\n"
        f"🕒 Ida: {u['Hora Ida']}\n"
        f"🕒 Regreso: {u['Hora Regreso']}\n"
        f"📱 Teléfono: {u['Telefono']}\n"
    )
    enviar_texto(to, resumen)


# ----------------- FLUJO DE CONVERSACIÓN -----------------

def procesar_flujo(to, texto, texto_lower):
    u = usuarios[to]

    if u["estado"] == "nombre":
        u["Nombre"] = texto
        u["estado"] = "correo"
        enviar_texto(to, "📧 ¿Cuál es tu correo de contacto?")

    elif u["estado"] == "correo":
        u["Correo"] = texto
        u["estado"] = "pasajeros"
        enviar_texto(to, "👥 ¿Cuántos pasajeros serán?")

    elif u["estado"] == "pasajeros":
        u["Pasajeros"] = texto
        u["estado"] = "fecha_viaje"
        enviar_texto(to, "📅 ¿En qué fecha necesitan el servicio? (Formato: DD-MM-AAAA, ej: 25-12-2025)")

    elif u["estado"] == "fecha_viaje":
        # Validación de fecha correcta
        try:
            fecha = datetime.strptime(texto, "%d-%m-%Y").date()
            if fecha < date.today():
                enviar_texto(to, "⚠️ La fecha ingresada ya pasó.\nPor favor ingresa una fecha futura en formato DD-MM-AAAA (ej: 25-12-2025).")
                return
            u["Fecha Viaje"] = fecha.strftime("%d-%m-%Y")
            u["estado"] = "origen"
            enviar_texto(to, "📍 ¿Desde dónde salen? (Dirección exacta)")
        except ValueError:
            enviar_texto(to, "⚠️ Formato de fecha no válido.\nPor favor ingresa la fecha en formato DD-MM-AAAA (ej: 25-12-2025).")
            return

    elif u["estado"] == "origen":
        u["Origen"] = texto
        u["estado"] = "destino"
        enviar_texto(to, "📍 ¿Hacia dónde se dirigen?")

    elif u["estado"] == "destino":
        u["Destino"] = texto
        u["estado"] = "hora_ida"
        enviar_texto(to, "🕒 ¿Hora aproximada de ida? (ej: 08:00)")

    elif u["estado"] == "hora_ida":
        u["Hora Ida"] = texto
        u["estado"] = "hora_vuelta"
        enviar_texto(to, "🕒 ¿Hora aproximada de regreso? (ej: 18:00)")

    elif u["estado"] == "hora_vuelta":
        u["Hora Regreso"] = texto
        u["estado"] = "telefono"
        enviar_texto(to, "📱 ¿Cuál es tu número de contacto?")

    elif u["estado"] == "telefono":
        u["Telefono"] = texto
        u["estado"] = "confirmar"
        mostrar_resumen(to)
        enviar_confirmacion(to)

    elif u["estado"] == "confirmar":
        if texto_lower in ["si", "sí", "s", "ok", "correcto", "confirmar_si"]:
            # Guardar en Google Sheets
            try:
                sheet.append_row([
                    datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    u['Nombre'],
                    u['Correo'],
                    u['Pasajeros'],
                    u['Fecha Viaje'],
                    u['Origen'],
                    u['Destino'],
                    u['Hora Ida'],
                    u['Hora Regreso'],
                    u['Telefono']
                ])
            except Exception as e:
                print("❌ Error guardando en Google Sheets:", e)

            # Enviar correo al ejecutivo
            enviar_email_cotizacion(u)

            enviar_texto(
                to,
                "🎉 *¡Cotización recibida!*\n"
                "Muy pronto un ejecutivo te contactará 🙌\n"
                "✉️ Revisa tu mail."
            )
            usuarios.pop(to, None)

        elif texto_lower in ["no", "n", "confirmar_no"]:
            usuarios[to]["estado"] = "corregir"
            enviar_texto(
                to,
                "Entiendo 👍 ¿Qué dato quieres corregir?\n\n"
                "1️⃣ Nombre\n"
                "2️⃣ Correo\n"
                "3️⃣ Pasajeros\n"
                "4️⃣ Fecha de viaje\n"
                "5️⃣ Origen\n"
                "6️⃣ Destino\n"
                "7️⃣ Hora de ida\n"
                "8️⃣ Hora de regreso\n"
                "9️⃣ Teléfono"
            )
        else:
            enviar_texto(to, "Por favor responde con *Sí* o *No* o usa los botones 😊")

    elif u["estado"] == "corregir":
        mapeo = {
            "1": "Nombre",
            "2": "Correo",
            "3": "Pasajeros",
            "4": "Fecha Viaje",
            "5": "Origen",
            "6": "Destino",
            "7": "Hora Ida",
            "8": "Hora Regreso",
            "9": "Telefono"
        }
        if texto_lower in mapeo:
            u["correccion"] = mapeo[texto_lower]
            u["estado"] = "re_ingreso"
            enviar_texto(to, f"Perfecto 😃\nNuevo valor para {mapeo[texto_lower]}:")
        else:
            enviar_texto(to, "Selecciona solo una opción del 1 al 9 😉")

    elif u["estado"] == "re_ingreso":
        campo = u.get("correccion")
        if campo:
            if campo == "Fecha Viaje":
                # Validar de nuevo fecha
                try:
                    fecha = datetime.strptime(texto, "%d-%m-%Y").date()
                    if fecha < date.today():
                        enviar_texto(to, "⚠️ La fecha ingresada ya pasó.\nPor favor ingresa una fecha futura en formato DD-MM-AAAA.")
                        return
                    usuarios[to]["Fecha Viaje"] = fecha.strftime("%d-%m-%Y")
                except ValueError:
                    enviar_texto(to, "⚠️ Formato de fecha no válido. Usa DD-MM-AAAA.")
                    return
            else:
                usuarios[to][campo] = texto

        usuarios[to].pop("correccion", None)
        usuarios[to]["estado"] = "confirmar"
        mostrar_resumen(to)
        enviar_confirmacion(to)


# ----------------- ENDPOINTS FLASK -----------------

@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot Ecobus Activo 🚍", 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    data = request.get_json()
    print("📩 DATA:", data)

    try:
        entry = data["entry"][0]["changes"][0]["value"]

        # Solo procesamos si hay mensajes
        if "messages" not in entry:
            print("📥 Evento sin 'messages', ignorado.")
            return jsonify({"status": "ignored"}), 200

        mensajes = entry["messages"]

        for m in mensajes:
            msg_type = m.get("type", "text")
            texto = ""
            # Soportar texto e interacciones con botones
            if msg_type == "text":
                texto = m["text"]["body"].strip()
            elif msg_type == "interactive":
                interactive = m.get("interactive", {})
                itype = interactive.get("type")
                if itype == "button_reply":
                    texto = interactive["button_reply"]["id"]
                elif itype == "list_reply":
                    texto = interactive["list_reply"]["id"]
            elif msg_type == "button":
                texto = m.get("button", {}).get("payload", "").strip() or m.get("button", {}).get("text", "").strip()

            if not texto:
                continue

            texto_lower = texto.lower()
            to = m["from"]

            if to not in usuarios:
                usuarios[to] = {"estado": None}

            # Saludo / menú
            if texto_lower in ["hola", "menu", "buenas", "hola ecobus", "hey"]:
                usuarios[to]["estado"] = None
                enviar_menu_principal(to)
                continue

            # Menú principal (botones o texto)
            if usuarios[to]["estado"] is None:
                if texto_lower in ["1", "cotizar"]:
                    usuarios[to] = {"estado": "nombre"}
                    enviar_texto(to, "Perfecto! 😊\n👤 ¿Cuál es tu nombre?")
                elif texto_lower in ["2", "ejecutivo"]:
                    enviar_texto(to, "📞 Puedes hablar con un ejecutivo al:\n+56 9 9871 1060")
                else:
                    enviar_menu_principal(to)
            else:
                procesar_flujo(to, texto, texto_lower)

    except Exception as e:
        print("❌ ERROR WEBHOOK:", e)

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(port=10000, debug=False)
