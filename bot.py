import os
import requests
import uuid
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
from pricing_engine import calcular_precio
from maps import geocode, route, geocode_candidates
from map_image import generar_mapa_static
from pricing_engine import calcular_precio, calcular_cotizacion_flotilla
from pricing_engine import resumen_flotilla



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
import base64
from pdf_generator import generar_pdf_cotizacion
from map_image import generar_mapa_static


import os
import base64
import requests

from pdf_generator import generar_pdf_cotizacion

def enviar_correo(usuario):
    try:
        SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
        if not SENDGRID_API_KEY:
            print("❌ Falta SENDGRID_API_KEY en variables de entorno")
            return False

        # ✅ Generar PDF
        pdf_path = generar_pdf_cotizacion(usuario)
        print("✅ PDF generado en:", pdf_path)

        with open(pdf_path, "rb") as f:
            pdf_base64 = base64.b64encode(f.read()).decode("utf-8")

        print("✅ PDF convertido a base64 (tamaño chars):", len(pdf_base64))

        cuerpo = (
            "Hola,\n\n"
            "Adjunto encontrarás la cotización solicitada. Para confirmar el servicio, responder este correo o comunicarse al +56997799101\n\n"
            f"ID Cotización: {usuario.get('cotizacion_id','')}\n"
            f"Origen: {usuario.get('Origen','')}\n"
            f"Destino: {usuario.get('Destino','')}\n"
            f"Pasajeros: {usuario.get('Pasajeros','')}\n"
            f"Total estimado: ${usuario.get('Precio','')}\n\n"
            "Ecobus / Ecovan\n"
        )

        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "personalizations": [
                {
                    "to": [{"email": usuario.get("Correo", "")}],
                    "cc": [{"email": NOTIFY_EMAIL}],
                    "subject": "Cotización Ecobus - Transporte Privado"
                }
            ],
            "from": {"email": FROM_EMAIL},
            "content": [
                {"type": "text/plain", "value": cuerpo}
            ],
            "attachments": [
                {
                    "content": pdf_base64,
                    "type": "application/pdf",
                    "filename": f"cotizacion_{usuario.get('cotizacion_id','')}.pdf",
                    "disposition": "attachment"
                }
            ]
        }

        # ✅ Adjuntar imagen del mapa SOLO si existe (sin recalcular nada)
        try:
            ruta_img = usuario.get("Mapa Ruta", "")
            if ruta_img and os.path.exists(ruta_img):
                with open(ruta_img, "rb") as f:
                    mapa_base64 = base64.b64encode(f.read()).decode("utf-8")

                payload["attachments"].append(
                    {
                        "content": mapa_base64,
                        "type": "image/png",
                        "filename": f"ruta_referencial_{usuario.get('cotizacion_id','')}.png",
                        "disposition": "attachment"
                    }
                )
                print("✅ Imagen de ruta adjunta al correo:", ruta_img)
            else:
                print("ℹ️ No hay imagen de ruta para adjuntar (Mapa Ruta vacío o no existe).")
        except Exception as e:
            print("⚠️ No se pudo adjuntar imagen del mapa:", e)

        r = requests.post(url, headers=headers, json=payload, timeout=20)

        if r.status_code == 202:
            print("📧 Correo enviado con PDF adjunto OK")
            return True

        print("❌ Error SendGrid:", r.status_code, r.text)
        return False

    except Exception as e:
        print("❌ Exception enviar_correo:", e)
        return False

# -------- MENÚ --------
def menu_principal(to):
    enviar_botones(to, "¡Hola! soy Javier , el asistente virtual de Ecobus. Cuentame, ¿Qué deseas hacer hoy? 🚍",
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

# -------- Cotizacion pendiente --------

def marcar_cotizacion_pendiente(u: dict, motivo: str):
    u["KM Total"] = "PENDIENTE"
    u["Horas Total"] = "PENDIENTE"
    u["Vehiculo"] = "PENDIENTE"
    u["Precio"] = "PENDIENTE"
    u["Error Cotizacion"] = motivo


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

        # ✅ Buscar candidatos para confirmar dirección
        try:
            candidatos = geocode_candidates(texto, limit=3)
        except Exception as e:
            print("⚠️ Error geocode_candidates origen:", e)
            candidatos = []

        # Si encontró 2 o más opciones, pedir confirmación
        if len(candidatos) >= 2:
            u["candidatos_origen"] = candidatos
            u["estado"] = "confirmar_origen"

            cuerpo = "📍 Confirmemos el *ORIGEN*. ¿Cuál es el correcto?"
            botones = []

            for i, cnd in enumerate(candidatos):
                title = cnd["name"][:20]  # WhatsApp button title tiene límite
                botones.append({"id": f"origen_opt_{i}", "title": title})

            return enviar_botones(to, cuerpo, botones)

        # Si encontró 1, seguimos sin preguntar
        u["estado"] = "destino"
        return enviar_texto(to, "🎯 ¿Destino?")

    if estado == "confirmar_origen":
        # El usuario eligió uno de los botones origen_opt_0,1,2
        if texto_lower.startswith("origen_opt_"):
            try:
                idx = int(texto_lower.split("_")[-1])
                candidatos = u.get("candidatos_origen", [])
                elegido = candidatos[idx]

                # Guardamos versión “bonita” del origen (texto)
                u["Origen"] = elegido["name"]

                # Guardamos coordenadas para no recalcular después
                u["Origen Lat"] = elegido["lat"]
                u["Origen Lon"] = elegido["lon"]

                u.pop("candidatos_origen", None)

                u["estado"] = "destino"
                return enviar_texto(to, "🎯 Perfecto. ¿Destino?")
            except Exception as e:
                print("⚠️ Error confirmando origen:", e)
                u["estado"] = "origen"
                return enviar_texto(to, "⚠️ No pude confirmar el origen. Escríbelo nuevamente:")


    # -------- DESTINO --------
    if estado == "destino":
        u["Destino"] = texto

        # ✅ Buscar candidatos para confirmar dirección
        try:
            candidatos = geocode_candidates(texto, limit=3)
        except Exception as e:
            print("⚠️ Error geocode_candidates destino:", e)
            candidatos = []

        if len(candidatos) >= 2:
            u["candidatos_destino"] = candidatos
            u["estado"] = "confirmar_destino"

            cuerpo = "🎯 Confirmemos el *DESTINO*. ¿Cuál es el correcto?"
            botones = []

            for i, cnd in enumerate(candidatos):
                title = cnd["name"][:20]
                botones.append({"id": f"destino_opt_{i}", "title": title})

            return enviar_botones(to, cuerpo, botones)

        u["estado"] = "ida"
        return enviar_texto(to, "🕒 Hora salida HH:MM")

    if estado == "confirmar_destino":
        if texto_lower.startswith("destino_opt_"):
            try:
                idx = int(texto_lower.split("_")[-1])
                candidatos = u.get("candidatos_destino", [])
                elegido = candidatos[idx]

                u["Destino"] = elegido["name"]
                u["Destino Lat"] = elegido["lat"]
                u["Destino Lon"] = elegido["lon"]

                u.pop("candidatos_destino", None)

                u["estado"] = "ida"
                return enviar_texto(to, "🕒 Perfecto. Hora salida HH:MM")
            except Exception as e:
                print("⚠️ Error confirmando destino:", e)
                u["estado"] = "destino"
                return enviar_texto(to, "⚠️ No pude confirmar el destino. Escríbelo nuevamente:")


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
            # 1. Geocoding (si el usuario confirmó con botones, ya tenemos coords)
            if "Origen Lat" in u and "Origen Lon" in u:
                lat_o, lon_o = u["Origen Lat"], u["Origen Lon"]
            else:
                lat_o, lon_o = geocode(u["Origen"])

            if "Destino Lat" in u and "Destino Lon" in u:
                lat_d, lon_d = u["Destino Lat"], u["Destino Lon"]
            else:
                lat_d, lon_d = geocode(u["Destino"])


            # 2. Ruta ida (3 valores)
            km_ida, horas_ida, poly_ida = route((lat_o, lon_o), (lat_d, lon_d))

            # 3. Ruta vuelta
            km_vuelta, horas_vuelta, poly_vuelta = route((lat_d, lon_d), (lat_o, lon_o))

            km_total = km_ida + km_vuelta
            horas_total = horas_ida + horas_vuelta

            # ✅ Guardar para PDF
            u["KM Total"] = round(km_total, 2)
            u["Horas Total"] = round(horas_total, 2)
            u["Polyline Ida"] = poly_ida

            # ✅ Generar imagen mapa
            try:
                ruta_img = generar_mapa_static(
                    (lat_o, lon_o),
                    (lat_d, lon_d),
                    u["Polyline Ida"],
                    u.get("cotizacion_id", "SINID")
                )
                u["Mapa Ruta"] = ruta_img
                print("✅ Imagen mapa generada en:", u["Mapa Ruta"])
            except Exception as e:
                print("⚠️ No se pudo generar imagen del mapa:", e)
                u["Mapa Ruta"] = ""

            # 4. Pricing
            if u["Pasajeros"] <= 45:
                resultado = calcular_precio(
                    km_total=km_total,
                    horas_total=horas_total,
                    pasajeros=u["Pasajeros"]
                )
                u["Vehiculo"] = resultado["vehiculo"]
                u["Precio"] = resultado["precio_final"]
                u["Detalle Vehiculos"] = ""  # para no romper tu PDF si no lo usa

            else:
                resultado = calcular_cotizacion_flotilla(
                    km_total=km_total,
                    horas_total=horas_total,
                    pasajeros=u["Pasajeros"]
                )


                # Texto “humano” del detalle (uno por línea) + resumen para no mostrar "MULTI"
                detalle_txt = []

                for item in resultado["items"]:
                    veh = item.get("vehiculo", "")
                    pax = item.get("pasajeros_asignados", 0)
                    precio_item = item.get("precio_final", 0)

                    # Nombre bonito (Bus/Van/Taxibus)
                    if veh == "bus":
                        nombre = "Bus"
                    elif veh == "van":
                        nombre = "Van"
                    elif veh == "taxibus":
                        nombre = "Taxibus"
                    else:
                        nombre = str(veh).capitalize()

                    # Línea limpia por vehículo (incluye precio por vehículo como tú querías)
                    detalle_txt.append(f"- {nombre} de {pax} pasajeros: ${precio_item}")

                # ✅ Vehiculo: resumen tipo "2 Buses + 1 Van" (NO "MULTI")
                # Si no tienes resumen_flotilla en pricing_engine, te dejo función abajo.
                u["Vehiculo"] = resumen_flotilla(resultado["items"])

                # ✅ Precio total final (igual que antes)
                u["Precio"] = resultado["precio_final_total"]

                # ✅ Detalle limpio para el PDF (NO diccionario feo)
                u["Detalle Vehiculos"] = "\n".join(detalle_txt)



            # 5. Guardar en usuario (NO pisar el detalle humano ni poner MULTI)
            # ✅ Precio total final
            if "precio_final_total" in resultado:
                u["Precio"] = round(resultado["precio_final_total"], 0)

            # ✅ Vehículo: si es flotilla usar resumen bonito, si es 1 vehículo usar nombre normal
            items = resultado.get("items", [])

            if len(items) == 1:
                u["Vehiculo"] = items[0].get("vehiculo", "")
            elif len(items) > 1:
                # Resumen bonito tipo: "1 bus (45 pax c/u) + 1 van (15 pax c/u)"
                u["Vehiculo"] = resumen_flotilla(items)

            # ✅ IMPORTANTE:
            # NO guardar lista/dict en "Detalle Vehiculos", porque el PDF lo imprime feo.
            # Aquí dejamos lo que ya se armó arriba como texto humano.
            # Si por algún motivo no existe, lo armamos aquí mismo.
            if not isinstance(u.get("Detalle Vehiculos", ""), str) or not u.get("Detalle Vehiculos", "").strip():
                detalle_txt = []
                for item in items:
                    veh = item.get("vehiculo", "")
                    pax = item.get("pasajeros_asignados", 0)
                    precio_item = item.get("precio_final", 0)

                    if veh == "bus":
                        nombre = "Bus"
                    elif veh == "van":
                        nombre = "Van"
                    elif veh == "taxibus":
                        nombre = "Taxibus"
                    else:
                        nombre = str(veh).capitalize()

                    detalle_txt.append(f"- {nombre} de {pax} pasajeros: ${precio_item}")

                u["Detalle Vehiculos"] = "\n".join(detalle_txt)

            u["Error Cotizacion"] = ""


        except Exception as e:
            print("❌ Error cotizando:", e)

            # ✅ PENDIENTE si falla
            u["KM Total"] = "PENDIENTE"
            u["Horas Total"] = "PENDIENTE"
            u["Vehiculo"] = "PENDIENTE"
            u["Precio"] = "PENDIENTE"
            u["Error Cotizacion"] = str(e)
            u["Mapa Ruta"] = ""

            enviar_texto(
                to,
                "⚠️ No pudimos calcular la ruta automáticamente.\n"
                "Tu solicitud fue registrada y un ejecutivo enviará la cotización manualmente."
            )

        # ✅ SIEMPRE guardar y enviar correo
        guardar_en_sheet(u)
        enviar_correo(u)

        enviar_texto(to, "✅ Solicitud enviada, RECUERDA REVISAR TUS CORREOS DE SPAM/NO DESEADOS. ¡Gracias!")
        usuarios.pop(to, None)
        return

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
