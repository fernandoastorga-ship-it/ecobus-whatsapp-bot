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
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "fabian@ecobus.cl")

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
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            usuario.get("cotizacion_id", ""),
            usuario.get("Nombre", ""),
            usuario.get("Correo", ""),
            usuario.get("Fecha Viaje", ""),
            usuario.get("Pasajeros", ""),
            usuario.get("Origen", ""),
            usuario.get("Destino", ""),
            usuario.get("Hora Ida", ""),
            usuario.get("Hora Regreso", ""),
            usuario.get("Telefono", ""),
            "ENVIADA",
            "",
        ]
        sheet.append_row(fila, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        print("❌ Error guardando en Google Sheets:", e)
        return False


def email_valido(c):
    c = c.strip()
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
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
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
                    {"type": "reply", "reply": b} for b in botones
                ]
            },
        },
    }
    requests.post(url, headers=headers, json=data)


def procesar_flujo(to, texto, texto_lower):
    u = usuarios[to]
    estado = u["estado"]

    if estado == "nombre":
        u["Nombre"] = texto
        u["estado"] = "correo"
        return enviar_texto(to, "📧 ¿Correo?")

    if estado == "correo":
        if not email_valido(texto):
            return enviar_texto(to, "Correo inválido")
        u["Correo"] = texto
        u["estado"] = "pasajeros"
        return enviar_texto(to, "👥 Pasajeros")

    if estado == "pasajeros":
        if not pasajeros_validos(texto):
            return enviar_texto(to, "Ingresa número válido")
        u["Pasajeros"] = int(texto)
        u["estado"] = "fecha"
        return enviar_texto(to, "📅 Fecha DD-MM-AAAA")

    if estado == "fecha":
        u["Fecha Viaje"] = texto
        u["estado"] = "origen"
        return enviar_texto(to, "📍 Origen")

    if estado == "origen":
        u["Origen"] = texto
        u["estado"] = "destino"
        return enviar_texto(to, "🎯 Destino")

    if estado == "destino":
        u["Destino"] = texto
        u["estado"] = "ida"
        return enviar_texto(to, "🕒 Hora ida")

    if estado == "ida":
        u["Hora Ida"] = texto
        u["estado"] = "regreso"
        return enviar_texto(to, "🕒 Hora regreso")

    if estado == "regreso":
        u["Hora Regreso"] = texto
        u["estado"] = "confirmar"
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
