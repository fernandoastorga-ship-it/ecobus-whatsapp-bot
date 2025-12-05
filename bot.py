import os
import requests
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import smtplib
from email.message import EmailMessage

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
# Por defecto, si no pones NOTIFY_EMAIL en Render, va a fabian@ecobus.cl
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

# Memoria simple de usuarios en RAM
usuarios = {}


# =========================
# UTILIDADES WHATSAPP
# =========================

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
    r = requests.post(url, headers=headers, json=data)
    print("📤 WhatsApp texto:", r.status_code, r.text)


def enviar_botones(to, cuerpo: str, botones):
    """
    Enviar mensaje interactivo con botones.
    botones: lista de dicts: [{"id": "cotizar", "title": "Cotizar viaje"}, ...]
    OJO: títulos máx 20 caracteres.
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
                        "reply": {
                            "id": b["id"],
                            "title": b["title"]
                        }
                    } for b in botones
                ]
            }
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print("📤 WhatsApp botones:", r.status_code, r.text)


def menu_principal(to):
    """Menú principal con botones (Cotizar / Ejecutivo)."""
    texto = "Hola 👋 Soy el asistente de *Ecobus* 🚍\n¿Qué quieres hacer hoy?"
    botones = [
        {"id": "cotizar", "title": "Cotizar viaje"},
        {"id": "ejecutivo", "title": "Ejecutivo"}
    ]
    enviar_botones(to, texto, botones)


def enviar_confirmacion(to):
    """Botones finales de confirmación."""
    texto = "¿Está todo correcto?"
    botones = [
        {"id": "confirmar_si", "title": "Sí"},
        {"id": "confirmar_no", "title": "No, corregir"}
    ]
    enviar_botones(to, texto, botones)


# =========================
# VALIDACIONES
# =========================

def email_valido(correo: str) -> bool:
    if "@" not in correo:
        return False
    parte_dom = correo.split("@")[-1]
    if "." not in parte_dom:
        return False
    return True


def hora_valida(hora_texto: str) -> bool:
    try:
        datetime.strptime(hora_texto.strip(), "%H:%M")
        return True
    except ValueError:
        return False


# =========================
# CORREO DE COTIZACIÓN
# =========================

def enviar_correo_notificacion(usuario):
    try:
        import smtplib
        from email.mime.text import MIMEText

        cuerpo = (
            "📬 Nueva solicitud de cotización recibida:\n\n"
            f"👤 Nombre: {usuario['Nombre']}\n"
            f"📧 Correo: {usuario['Correo']}\n"
            f"📅 Fecha del viaje: {usuario['Fecha']}\n"
            f"👥 Pasajeros: {usuario['Pasajeros']}\n"
            f"📍 Origen: {usuario['Origen']}\n"
            f"🎯 Destino: {usuario['Destino']}\n"
            f"🕒 Ida: {usuario['Hora Ida']}\n"
            f"🕒 Regreso: {usuario['Hora Regreso']}\n"
            f"📱 Contacto: {usuario['Telefono']}\n"
        )

        msg = MIMEText(cuerpo, "plain", "utf-8")
        msg["Subject"] = "Nueva solicitud de cotización - Ecobus"
        msg["From"] = FROM_EMAIL
        msg["To"] = NOTIFY_EMAIL

        print("📬 Intentando enviar correo...")

        server = smtplib.SMTP(SMTP_HOST, int(SMTP_PORT))
        server.ehlo()
        server.starttls()  # ✔ Necesario para Gmail
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, NOTIFY_EMAIL, msg.as_string())
        server.quit()

        print("📧 Correo enviado correctamente a", NOTIFY_EMAIL)

    except Exception as e:
        print("⚠️ Error enviando correo:", str(e))


# =========================
# RESUMEN
# =========================

def mostrar_resumen(to):
    u = usuarios[to]
    resumen = (
        "🔥 *Resumen del viaje solicitado*:\n\n"
        f"👤 Nombre: {u.get('Nombre','')}\n"
        f"📧 Correo: {u.get('Correo','')}\n"
        f"👥 Pasajeros: {u.get('Pasajeros','')}\n"
        f"📅 Fecha del viaje: {u.get('Fecha Viaje','')}\n"
        f"📍 Origen: {u.get('Origen','')}\n"
        f"🎯 Destino: {u.get('Destino','')}\n"
        f"🕒 Ida: {u.get('Hora Ida','')}\n"
        f"🕒 Regreso: {u.get('Hora Regreso','')}\n"
        f"📱 Teléfono: {u.get('Telefono','')}\n"
    )
    enviar_texto(to, resumen)


# =========================
# FLUJO PRINCIPAL
# =========================

def procesar_flujo(to, texto, texto_lower):
    u = usuarios[to]

    # 1) Nombre
    if u["estado"] == "nombre":
        u["Nombre"] = texto
        u["estado"] = "correo"
        enviar_texto(to, "📧 ¿Cuál es tu correo de contacto?")

    # 2) Correo (con validación simple)
    elif u["estado"] == "correo":
        if not email_valido(texto):
            enviar_texto(
                to,
                "⚠️ El correo no parece válido.\n"
                "Ejemplo: cliente@empresa.cl\n"
                "Por favor ingrésalo nuevamente:"
            )
            return
        u["Correo"] = texto
        u["estado"] = "pasajeros"
        enviar_texto(to, "👥 ¿Cuántos pasajeros serán?")

    # 3) Pasajeros (texto libre, como antes)
    elif u["estado"] == "pasajeros":
        u["Pasajeros"] = texto
        u["estado"] = "fecha_viaje"
        enviar_texto(
            to,
            "📅 ¿En qué fecha necesitan el servicio?\n"
            "Formato: DD-MM-AAAA (ejemplo: 25-12-2025)"
        )

    # 4) Fecha del viaje (validación formato y futura)
    elif u["estado"] == "fecha_viaje":
        try:
            fecha = datetime.strptime(texto, "%d-%m-%Y").date()
            if fecha < date.today():
                enviar_texto(
                    to,
                    "⚠️ La fecha ingresada ya pasó.\n"
                    "Por favor ingresa una fecha futura en formato DD-MM-AAAA.\n"
                    "Ejemplo: 25-12-2025"
                )
                return
            u["Fecha Viaje"] = fecha.strftime("%d-%m-%Y")
            u["estado"] = "origen"
            enviar_texto(
                to,
                "📍 ¿Desde dónde salen?\n"
                "Puedes escribir la dirección o compartir tu ubicación."
            )
        except ValueError:
            enviar_texto(
                to,
                "⚠️ Formato de fecha no válido.\n"
                "Usa el formato DD-MM-AAAA.\n"
                "Ejemplo: 25-12-2025"
            )
            return

    # 5) Origen
    elif u["estado"] == "origen":
        u["Origen"] = texto
        u["estado"] = "destino"
        enviar_texto(
            to,
            "📍 ¿Hacia dónde se dirigen?\n"
            "Puedes escribir la dirección o compartir la ubicación de destino."
        )

    # 6) Destino
    elif u["estado"] == "destino":
        u["Destino"] = texto
        u["estado"] = "hora_ida"
        enviar_texto(
            to,
            "🕒 ¿Hora aproximada de ida?\n"
            "Formato: HH:MM (ejemplo: 08:30)"
        )

    # 7) Hora ida (validar HH:MM)
    elif u["estado"] == "hora_ida":
        if not hora_valida(texto):
            enviar_texto(
                to,
                "⚠️ La hora no es válida.\n"
                "Usa formato HH:MM, por ejemplo: 08:30"
            )
            return
        u["Hora Ida"] = texto
        u["estado"] = "hora_vuelta"
        enviar_texto(
            to,
            "🕒 ¿Hora aproximada de regreso?\n"
            "Formato: HH:MM (ejemplo: 18:00)"
        )

    # 8) Hora vuelta (validar HH:MM)
    elif u["estado"] == "hora_vuelta":
        if not hora_valida(texto):
            enviar_texto(
                to,
                "⚠️ La hora no es válida.\n"
                "Usa formato HH:MM, por ejemplo: 18:00"
            )
            return
        u["Hora Regreso"] = texto
        u["estado"] = "telefono"
        enviar_texto(
            to,
            "📱 ¿Cuál es tu número de contacto?\n"
            "Si es el mismo desde el que escribes, puedes repetirlo."
        )

    # 9) Teléfono
    elif u["estado"] == "telefono":
        u["Telefono"] = texto
        u["estado"] = "confirmar"
        mostrar_resumen(to)
        enviar_confirmacion(to)

    # 10) Confirmación (Sí / No)
    elif usuario["estado"] == "confirmar":
        if texto.lower() in ["si", "sí", "correcto"]:

            try:
                sheet.append_row([
                    datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    usuario[to]['Nombre'],
                    usuario[to]['Correo'],
                    usuario[to]['Fecha'],
                    usuario[to]['Pasajeros'],
                    usuario[to]['Origen'],
                    usuario[to]['Destino'],
                    usuario[to]['Hora Ida'],
                    usuario[to]['Hora Regreso'],
                    usuario[to]['Telefono']
                ])

                enviar_correo_notificacion(usuario)

                enviar(to,
                    "🎉 *¡Solicitud recibida exitosamente!*\n"
                    "Estamos preparando tu cotización 🚍\n"
                    "📧 Revisa tu correo, ahí te llegará toda la información.\n"
                    "Un ejecutivo te contactará pronto 🙌"
                )

            except Exception as e:
                print("❌ ERROR finales:", str(e))

            usuarios.pop(to)
        else:
            enviar(to, "👌 No hay problema, vamos nuevamente 🚍")
            usuarios.pop(to)
            menu_principal(to)
            return "ok", 200

            # 1) SIEMPRE avisamos al cliente primero
            enviar_texto(
                to,
                "🎉 *¡Solicitud recibida exitosamente!*\n"
                "Estamos preparando tu cotización 🚍\n"
                "Un ejecutivo se pondrá en contacto contigo.\n"
                "📧 Revisa tu correo, ahí te llegará el detalle de la cotización."
            )

            # 2) Intentamos guardar en Google Sheets
            try:
                sheet.append_row([
                    datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    u.get('Nombre', ''),
                    u.get('Correo', ''),
                    u.get('Pasajeros', ''),
                    u.get('Fecha Viaje', ''),
                    u.get('Origen', ''),
                    u.get('Destino', ''),
                    u.get('Hora Ida', ''),
                    u.get('Hora Regreso', ''),
                    u.get('Telefono', '')
                ])
            except Exception as e:
                print("❌ Error guardando en Google Sheets:", e)

            # 3) Intentamos enviar correo (y si falla, solo lo anotamos en logs)
            enviar_correo_notificacion(usuario)


            # 4) Cerramos flujo del usuario
            usuarios.pop(to, None)

            menu_principal(to)

        else:
            enviar_texto(
                to,
                "Por favor responde *Sí* o *No*, o usa los botones de confirmación 😊"
            )


# =========================
# RUTAS FLASK
# =========================

@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot Ecobus Activo 🚍", 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Verificación de webhook
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    data = request.get_json()
    print("📩 DATA:", data)

    try:
        entry = data["entry"][0]["changes"][0]["value"]

        # Si no hay mensajes (puede ser status, etc.), ignoramos
        if "messages" not in entry:
            print("📥 Evento sin 'messages', ignorado.")
            return jsonify({"status": "ignored"}), 200

        mensajes = entry["messages"]

        for m in mensajes:
            msg_type = m.get("type", "text")
            texto = ""
            texto_lower = ""
            wa_from = m.get("from")

            if wa_from not in usuarios:
                usuarios[wa_from] = {"estado": None}

            # 1) Texto normal
            if msg_type == "text":
                texto = m["text"]["body"].strip()

            # 2) Botones interactivos
            elif msg_type == "interactive":
                interactive = m.get("interactive", {})
                itype = interactive.get("type")
                if itype == "button_reply":
                    texto = interactive["button_reply"]["id"]

            # 3) Ubicación
            elif msg_type == "location":
                loc = m.get("location", {})
                lat = loc.get("latitude")
                lng = loc.get("longitude")
                texto = f"Ubicación: {lat}, {lng}"

            # Si no pudimos obtener texto útil, saltamos
            if not texto:
                continue

            texto_lower = texto.lower()

            # Palabras de saludo / menú
            if texto_lower in ["hola", "menu", "buenas", "hola ecobus", "hey"]:
                usuarios[wa_from]["estado"] = None
                menu_principal(wa_from)
                continue

            # Si no hay estado (inicio de flujo) → menú principal / opciones
            if usuarios[wa_from]["estado"] is None:
                # Menú: Cotizar
                if texto_lower in ["1", "cotizar"]:
                    usuarios[wa_from] = {"estado": "nombre"}
                    enviar_texto(wa_from, "Perfecto! 😊\n👤 ¿Cuál es tu nombre?")
                # Menú: Ejecutivo
                elif texto_lower in ["2", "ejecutivo"]:
                    enviar_texto(
                        wa_from,
                        "📞 Un ejecutivo te puede atender aquí:\n+56 9 9871 1060"
                    )
                else:
                    menu_principal(wa_from)
            else:
                # Continuar flujo
                procesar_flujo(wa_from, texto, texto_lower)

    except Exception as e:
        print("❌ ERROR WEBHOOK:", e)

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(port=10000, debug=False)
