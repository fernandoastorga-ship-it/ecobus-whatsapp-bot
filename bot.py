import os
import requests
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)

# Variables de entorno
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ecobus_token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")

# Conexión Google Sheets (estable y probada)
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(credentials)
worksheet = client.open_by_key(GOOGLE_SHEETS_ID).get_worksheet(0)

# Memoria temporal
usuarios = {}


# 📤 Enviar mensaje
def enviar(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to, "text": {"body": message}}
    response = requests.post(url, headers=headers, json=data)
    print(f"📤 Enviado a {to}: {message}")
    print("🔍 WhatsApp API:", response.status_code, response.text)


# 🏠 Menú principal
def menu_principal(to):
    usuarios[to]["estado"] = None
    enviar(to,
        "Hola 👋 Soy el asistente de Ecobus 🚍\n"
        "¿Qué quieres hacer?\n\n"
        "1️⃣ Cotizar un viaje\n"
        "2️⃣ Hablar con un ejecutivo 👨‍💼"
    )


# 🧾 Mostrar resumen
def mostrar_resumen(to):
    u = usuarios[to]
    resumen = (
        "🔥 Resumen del viaje solicitado:\n\n"
        f"👤 Nombre: {u['Nombre']}\n"
        f"📧 Correo: {u['Correo']}\n"
        f"👥 Pasajeros: {u['Pasajeros']}\n"
        f"📍 Origen: {u['Origen']}\n"
        f"🎯 Destino: {u['Destino']}\n"
        f"🕒 Ida: {u['Hora Ida']}\n"
        f"🕒 Regreso: {u['Hora Regreso']}\n"
        f"📱 Teléfono: {u['Telefono']}\n\n"
        "¿Está todo correcto? (Sí/No)"
    )
    enviar(to, resumen)


# 🔁 Flujo del usuario
def procesar_flujo(to, texto, texto_lower):
    u = usuarios[to]

    if u["estado"] == "nombre":
        u["Nombre"] = texto
        u["estado"] = "correo"
        enviar(to, "📧 ¿Cuál es tu correo de contacto?")

    elif u["estado"] == "correo":
        u["Correo"] = texto
        u["estado"] = "pasajeros"
        enviar(to, "👥 ¿Cuántos pasajeros serán?")

    elif u["estado"] == "pasajeros":
        u["Pasajeros"] = texto
        u["estado"] = "origen"
        enviar(to, "📍 ¿Desde dónde salen? (Dirección exacta)")

    elif u["estado"] == "origen":
        u["Origen"] = texto
        u["estado"] = "destino"
        enviar(to, "📍 ¿Hacia dónde se dirigen?")

    elif u["estado"] == "destino":
        u["Destino"] = texto
        u["estado"] = "hora_ida"
        enviar(to, "🕒 ¿Hora aproximada de ida?")

    elif u["estado"] == "hora_ida":
        u["Hora Ida"] = texto
        u["estado"] = "hora_vuelta"
        enviar(to, "🕒 ¿Hora de regreso?")

    elif u["estado"] == "hora_vuelta":
        u["Hora Regreso"] = texto
        u["estado"] = "telefono"
        enviar(to, "📱 Confírmame tu número telefónico de contacto")

    elif u["estado"] == "telefono":
        u["Telefono"] = texto
        u["estado"] = "confirmar"
        mostrar_resumen(to)

    elif u["estado"] == "confirmar":
        if texto_lower in ["si", "sí", "s", "correcto"]:
            try:
                worksheet.append_row([
                    datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    u['Nombre'], u['Correo'],
                    u['Pasajeros'], u['Origen'],
                    u['Destino'], u['Hora Ida'],
                    u['Hora Regreso'], u['Telefono']
                ])
                enviar(to, "🎉 ¡Cotización recibida! Muy pronto un ejecutivo te contactará 🙌\n✉️ Revisa tu mail !")
            except Exception as e:
                print("❌ Error guardando en Sheets:", e)
                enviar(to, "⚠️ Error guardando datos, pero ya recibimos tu solicitud.")
            usuarios.pop(to)
        
        elif texto_lower in ["no", "n"]:
            u["estado"] = "corregir"
            enviar(to,
                "Entiendo 👍 ¿Qué dato quieres corregir?\n\n"
                "1️⃣ Nombre\n"
                "2️⃣ Correo\n"
                "3️⃣ Pasajeros\n"
                "4️⃣ Origen\n"
                "5️⃣ Destino\n"
                "6️⃣ Hora de ida\n"
                "7️⃣ Hora de regreso\n"
                "8️⃣ Teléfono"
            )
        else:
            enviar(to, "Por favor responde: Sí o No 😄")

    elif u["estado"] == "corregir":
        mapeo = {
            "1": "Nombre",
            "2": "Correo",
            "3": "Pasajeros",
            "4": "Origen",
            "5": "Destino",
            "6": "Hora Ida",
            "7": "Hora Regreso",
            "8": "Telefono"
        }
        if texto_lower in mapeo:
            u["correccion"] = mapeo[texto_lower]
            u["estado"] = "re_ingreso"
            enviar(to, f"Perfecto 😃\nNuevo valor para {mapeo[texto_lower]}:")
        else:
            enviar(to, "Selecciona solo una opción del 1 al 8 😉")

    elif u["estado"] == "re_ingreso":
        campo = u["correccion"]
        u[campo] = texto
        u.pop("correccion")
        u["estado"] = "confirmar"
        mostrar_resumen(to)


@app.route("/", methods=["GET"])
def home():
    return "🤖 Ecobus Bot Operativo", 200


# 📬 Webhook WhatsApp
@app.route("/webhook", methods=["GET", "POST"])
def webhook_metodo():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    data = request.get_json()
    print("📩 DATA:", data)

    try:
        mensajes = data["entry"][0]["changes"][0]["value"]["messages"]
        for m in mensajes:
            texto = m["text"]["body"].strip()
            texto_lower = texto.lower()
            to = m["from"]

            if to not in usuarios:
                usuarios[to] = {"estado": None}

            if texto_lower in ["hola", "menu", "buenas", "hey", "hola ecobus"]:
                return menu_principal(to) or ("ok", 200)

            if usuarios[to]["estado"] is None:
                if texto_lower == "1":
                    usuarios[to]["estado"] = "nombre"
                    enviar(to, "Perfecto! 😊 Empecemos.\n👤 ¿Cuál es tu nombre?")
                elif texto_lower == "2":
                    enviar(to, "📞 Puedes hablar con un ejecutivo al:\n+56 9 9871 1060")
                else:
                    menu_principal(to)
            else:
                procesar_flujo(to, texto, texto_lower)

    except Exception as e:
        print("❌ ERROR WEBHOOK:", e)

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(port=10000, debug=True)
