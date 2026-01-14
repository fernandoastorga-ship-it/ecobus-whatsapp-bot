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

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ecobus_token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")

FROM_EMAIL = os.getenv("FROM_EMAIL")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "f.astorgasanmartin@gmail.com")

# GOOGLE SHEETS
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials.json", scope
)
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
    return p.strip().isdigit() and int(p) > 0


def enviar_texto(to, msg):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
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

    try:
        r = requests.post(url, headers=headers, json=data, timeout=10)
        if r.status_code >= 300:
            print("❌ Error WhatsApp enviar_botones:", r.status_code, r.text)
        return r
    except Exception as e:
        print("❌ Exception WhatsApp enviar_botones:", e)
        return None

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
        return enviar_botones(
            to,
            "¿Confirmar cotización?",
            [
                {"id": "confirmar_si", "title": "Sí"},
                {"id": "confirmar_no", "title": "No"},
            ],
        )

    # ✅ CONFIRMAR (CORRECTAMENTE DENTRO DE LA FUNCIÓN)
    if estado == "confirmar" and texto_lower == "confirmar_si":
        u["cotizacion_id"] = str(uuid.uuid4())[:8].upper()

        try:
            lat_o, lon_o = geocode(u["Origen"])
            lat_d, lon_d = geocode(u["Destino"])

            km_ida, h_ida = route((lat_o, lon_o), (lat_d, lon_d))
            km_v, h_v = route((lat_d, lon_d), (lat_o, lon_o))

            km_total = km_ida + km_vuelta
            horas_total = horas_ida + horas_vuelta

            resultado = calcular_precio(
                km_total=km_ida + km_v,
                horas_total=h_ida + h_v,
                pasajeros=u["Pasajeros"],
            )

            u.update(resultado)

        except Exception as e:
            print("❌ Error cotizando:", e)

        guardar_en_sheet(u)
        enviar_texto(to, "✅ Cotización enviada")
        usuarios.pop(to, None)


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Error", 403

    data = request.get_json()
    mensajes = (
        data.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("messages", [])
    )

    for m in mensajes:
        wa_id = m.get("from")
        texto = (
            m["text"]["body"]
            if m.get("type") == "text"
            else m.get("interactive", {})
            .get("button_reply", {})
            .get("id", "")
        )

        if wa_id not in usuarios:
            usuarios[wa_id] = {"estado": "nombre"}

        procesar_flujo(wa_id, texto, texto.lower())

    return jsonify({"status": "ok"}), 200
