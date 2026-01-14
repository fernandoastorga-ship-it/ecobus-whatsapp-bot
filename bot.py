import os
import requests
import uuid
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
from pricing_engine import calcular_precio
from maps import geocode, route
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

def guardar_en_sheet(usuario):
    try:
        fila = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Timestamp
            usuario.get("cotizacion_id", ""),              # ID Cotización
            usuario.get("Nombre", ""),
            usuario.get("Correo", ""),
            usuario.get("Fecha Viaje", ""),
            usuario.get("Pasajeros", ""),
            usuario.get("Origen", ""),
            usuario.get("Destino", ""),
            usuario.get("Hora Ida", ""),
            usuario.get("Hora Regreso", ""),
            usuario.get("Telefono", ""),
            "ENVIADA",                                     # Estado
            ""                                             # Fecha Respuesta
        ]

        sheet.append_row(fila, value_input_option="USER_ENTERED")
        print("✅ Guardado en Google Sheets OK:", fila)
        return True

    except Exception as e:
        print("❌ Error guardando en Google Sheets:", e)
        return False


# -------- Validaciones --------
def email_valido(c):
    # Quitar espacios al inicio y final
    c = c.strip()

    # No permitir saltos de línea ni espacios internos
    if "\n" in c or " " in c:
        return False

    # Regex simple y segura para email
    patron = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return bool(re.match(patron, c))

def pasajeros_validos(p):
    p = p.strip()
    return p.isdigit() and int(p) > 0


# -------- WhatsApp --------
def enviar_texto(to, msg):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}",
               "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to, "text": {"body": msg}}

    try:
        r = requests.post(url, headers=headers, json=data, timeout=10)
        if r.status_code >= 300:
            print("❌ Error WhatsApp enviar_texto:", r.status_code, r.text)
        return r
    except Exception as e:
        print("❌ Exception WhatsApp enviar_texto:", e)
        return None


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

    try:
        r = requests.post(url, headers=headers, json=data, timeout=10)
        if r.status_code >= 300:
            print("❌ Error WhatsApp enviar_botones:", r.status_code, r.text)
        return r
    except Exception as e:
        print("❌ Exception WhatsApp enviar_botones:", e)
        return None


# -------- Email --------
def enviar_correo(usuario):
    try:
        SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
        if not SENDGRID_API_KEY:
            print("❌ Falta SENDGRID_API_KEY en variables de entorno")
            return False

        # 🔗 Link de seguimiento (usa tu dominio real de Render)
        link_seguimiento = (
            f"https://ecobus-whatsapp-bot.onrender.com/seguimiento"
            f"?id={usuario.get('cotizacion_id','')}"
        )

        # 📧 Cuerpo del correo
        cuerpo = (
            "Nueva solicitud de cotización - Ecobus\n\n"
            f"Nombre: {usuario.get('Nombre','')}\n"
            f"Correo: {usuario.get('Correo','')}\n"
            f"Fecha viaje: {usuario.get('Fecha Viaje','')}\n"
            f"Pasajeros: {usuario.get('Pasajeros','')}\n"
            f"Origen: {usuario.get('Origen','')}\n"
            f"Destino: {usuario.get('Destino','')}\n"
            f"Hora ida: {usuario.get('Hora Ida','')}\n"
            f"Hora regreso: {usuario.get('Hora Regreso','')}\n"
            f"Teléfono: {usuario.get('Telefono','')}\n"
            "\n----------------------------------\n"
            "👉 Marcar cotización como RESPONDIDA:\n"
            f"{link_seguimiento}\n"
        )

        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "personalizations": [
                {
                    "to": [{"email": NOTIFY_EMAIL}],
                    "subject": "🚍 Nueva cotización recibida - Ecobus"
                }
            ],
            "from": {"email": FROM_EMAIL},
            "content": [
                {"type": "text/plain", "value": cuerpo}
            ]
        }

        r = requests.post(url, headers=headers, json=payload, timeout=20)

        if r.status_code == 202:
            print("📧 Correo SendGrid enviado correctamente")
            return True

        print("❌ Error SendGrid:", r.status_code, r.text)
        return False

    except Exception as e:
        print("❌ Exception enviar_correo (SendGrid):", e)
        return False


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
        "telefono": "telefono",
        "ida": "ida",
        "regreso": "regreso",
    }

    for key, estado in mapping.items():
        if f"cambiar {key}" in texto_lower:
            usuarios[to]["estado"] = estado
            usuarios[to]["modo_correccion"] = True
            enviar_texto(to, f"Ok 👍 Envíame el nuevo {key}:")
            return True

    return False

def procesar_flujo(to, texto, texto_lower):
    u = usuarios[to]

    if corregir_campos(to, texto_lower):
        return

    estado = u["estado"]

    # -------- NOMBRE --------
    if estado == "nombre":
        u["Nombre"] = texto
        u["estado"] = "correo"
        return enviar_texto(to, "📧 ¿Cuál es su correo?")

    # -------- CORREO --------
    if estado == "correo":
        if not email_valido(texto):
            return enviar_texto(
                to,
                "⚠️ Correo inválido.\n"
                "Ingresa solo el correo, una línea.\n"
                "Ej: nombre@empresa.cl"
            )

        u["Correo"] = texto
        u["estado"] = "pasajeros"
        return enviar_texto(to, "👥 ¿Cuántos pasajeros?")

    # -------- PASAJEROS --------
    if estado == "pasajeros":
        if not pasajeros_validos(texto):
            return enviar_texto(to, "⚠️ Ingresa solo un número. Ej: 12")

        u["Pasajeros"] = int(texto)
        u["estado"] = "fecha"
        return enviar_texto(to, "📅 Fecha DD-MM-AAAA")

    # -------- FECHA --------
    if estado == "fecha":
        try:
            f = datetime.strptime(texto, "%d-%m-%Y").date()
            if f < date.today():
                return enviar_texto(to, "Fecha futura por favor")

            u["Fecha Viaje"] = f.strftime("%d-%m-%Y")
            u["estado"] = "origen"
            return enviar_texto(to, "📍 ¿Desde dónde salen?")
        except:
            return enviar_texto(to, "Formato inválido. Ej: 25-12-2026")

    # -------- ORIGEN --------
    if estado == "origen":
        u["Origen"] = texto
        u["estado"] = "destino"
        return enviar_texto(to, "🎯 ¿Destino?")

    # -------- DESTINO --------
    if estado == "destino":
        u["Destino"] = texto
        u["estado"] = "ida"
        return enviar_texto(to, "🕒 Hora salida HH:MM")

    # -------- IDA --------
    if estado == "ida":
        u["Hora Ida"] = texto
        u["estado"] = "regreso"
        return enviar_texto(to, "🕒 Hora regreso HH:MM")

    # -------- REGRESO --------
    if estado == "regreso":
        u["Hora Regreso"] = texto
        u["estado"] = "telefono"
        return enviar_texto(to, "📱 Teléfono")

    # -------- TELÉFONO --------
    if estado == "telefono":
        u["Telefono"] = texto
        u["estado"] = "confirmar"
        mostrar_resumen(to)
        return enviar_confirmacion(to)

# -------- CONFIRMAR --------
if estado == "confirmar" and texto_lower == "confirmar_si":
    u["cotizacion_id"] = str(uuid.uuid4())[:8].upper()

    try:
        # 1. Geocoding
        lat_o, lon_o = geocode(u["Origen"])
        lat_d, lon_d = geocode(u["Destino"])

        # 2. Ruta ida
        km_ida, horas_ida = route((lat_o, lon_o), (lat_d, lon_d))

        # 3. Ruta vuelta (siempre)
        km_vuelta, horas_vuelta = route((lat_d, lon_d), (lat_o, lon_o))

        km_total = km_ida + km_vuelta
        horas_total = horas_ida + horas_vuelta

        # 4. Pricing
        resultado = calcular_precio(
            km_total=km_total,
            horas_total=horas_total,
            pasajeros=u["Pasajeros"]
        )

        # 5. Guardar en usuario
        u["KM Total"] = round(km_total, 2)
        u["Horas Total"] = round(horas_total, 2)
        u["Vehiculo"] = resultado["vehiculo"]
        u["Precio"] = resultado["precio_final"]

    except Exception as e:
        print("❌ Error cotizando:", e)
        enviar_texto(to, "⚠️ No pudimos calcular la ruta. Un ejecutivo revisará tu solicitud.")
        guardar_en_sheet(u)
        enviar_correo(u)
        usuarios.pop(to, None)
        return

    guardar_en_sheet(u)
    enviar_correo(u)
    enviar_texto(to, "✅ Cotización enviada. Te contactaremos a la brevedad.")
    usuarios.pop(to, None)

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

        elif tipo == "location":
            lat = m["location"]["latitude"]
            lon = m["location"]["longitude"]
            texto = f"{lat},{lon}"

        else:
            texto = ""

        texto_lower = texto.lower()

        if wa_id not in usuarios:
            usuarios[wa_id] = {
                "estado": None,
                "modo_correccion": False
            }

        if texto_lower in ["hola", "menú", "menu", "inicio"]:
            usuarios[wa_id]["estado"] = None
            menu_principal(wa_id)
            continue

        if usuarios[wa_id]["estado"] is None:
            if texto_lower == "cotizar":
                usuarios[wa_id]["estado"] = "nombre"
                enviar_texto(wa_id, "👤 Nombre de la persona/empresa solicitante")
            elif texto_lower == "ejecutivo":
                enviar_texto(
                    wa_id,
                    "Perfecto, Fabian será el ejecutivo encargado 📞 +56 9 9871 1060"
                )
            else:
                menu_principal(wa_id)
        else:
            procesar_flujo(wa_id, texto, texto_lower)

    # 🔴 ESTE return DEBE QUEDAR DENTRO DE LA FUNCIÓN
    return jsonify({"status": "ok"}), 200
