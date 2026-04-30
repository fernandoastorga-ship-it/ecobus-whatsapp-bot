import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from datetime import datetime
from reportlab.lib.utils import ImageReader


def generar_pdf_cotizacion(usuario: dict) -> str:
    cot_id = usuario.get("cotizacion_id", "SINID")

    filename = f"cotizacion_{cot_id}.pdf"
    output_path = os.path.join("/tmp", filename)

    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    # -------------------------
    # LOGO DE FONDO (OPCIONAL)
    # -------------------------
    logo_path = "logo_ecobus.png"  # 👈 pon aquí tu logo PNG
    if os.path.exists(logo_path):
        try:
            c.drawImage(
                ImageReader(logo_path),
                width / 2 - 8 * cm,
                height / 2 - 8 * cm,
                width=16 * cm,
                height=16 * cm,
                mask='auto'
            )
        except:
            pass

    # -------------------------
    # HEADER
    # -------------------------
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, height - 2.2 * cm, "COTIZACIÓN DE TRANSPORTE - ECOBUS")

    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, height - 2.9 * cm, f"Fecha emisión: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    c.drawString(2 * cm, height - 3.4 * cm, f"ID Cotización: {cot_id}")

    y = height - 4.5 * cm

    # -------------------------
    # Datos solicitante
    # -------------------------
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Datos del solicitante")
    y -= 0.6 * cm

    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, f"Nombre: {usuario.get('Nombre', '')}")
    y -= 0.45 * cm
    c.drawString(2 * cm, y, f"Correo: {usuario.get('Correo', '')}")
    y -= 0.45 * cm
    c.drawString(2 * cm, y, f"Teléfono: {usuario.get('Telefono', '')}")

    # -------------------------
    # DETALLE DEL VIAJE (NUEVO)
    # -------------------------
    y -= 0.8 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Detalles del viaje")
    y -= 0.6 * cm

    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, f"Fecha viaje: {usuario.get('Fecha Viaje', '')}")
    y -= 0.45 * cm
    c.drawString(2 * cm, y, f"Pasajeros: {usuario.get('Pasajeros', '')}")
    y -= 0.45 * cm
    c.drawString(2 * cm, y, f"Origen: {usuario.get('Origen', '')}")
    y -= 0.45 * cm
    c.drawString(2 * cm, y, f"Destino: {usuario.get('Destino', '')}")
    y -= 0.45 * cm
    c.drawString(2 * cm, y, f"Horario: {usuario.get('Hora Ida', '')} - {usuario.get('Hora Regreso', '')}")
    y -= 0.6 * cm

    # -------------------------
    # VEHÍCULOS (CAMBIADO)
    # -------------------------
    vehiculo_txt = usuario.get("Vehiculo", "")
    c.drawString(2 * cm, y, f"Vehículo/s asignados: {vehiculo_txt}")
    y -= 0.6 * cm

    # -------------------------
    # DETALLE VEHÍCULOS
    # -------------------------
    detalle_raw = usuario.get("Detalle Vehiculos", "")

    if isinstance(detalle_raw, list):
        detalle_txt = "\n".join(str(x) for x in detalle_raw).strip()
    else:
        detalle_txt = str(detalle_raw).strip()

    if detalle_txt:
        c.setFont("Helvetica", 10)
        for linea in detalle_txt.split("\n"):
            c.drawString(2.3 * cm, y, linea)
            y -= 0.4 * cm

        y -= 0.2 * cm

    # -------------------------
    # TOTAL (REUBICADO)
    # -------------------------
    precio_txt = usuario.get("Precio", "")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, f"Total estimado: ${precio_txt}")

    # -------------------------
    # MAPA
    # -------------------------
    y -= 1.2 * cm
    ruta_img = usuario.get("Mapa Ruta", "")

    if ruta_img and os.path.exists(ruta_img):
        try:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(2 * cm, y, "Mapa referencial del recorrido")
            y -= 0.5 * cm

            img_width = 17 * cm
            img_height = 7.5 * cm

            c.drawImage(
                ImageReader(ruta_img),
                2 * cm,
                y - img_height,
                width=img_width,
                height=img_height,
                preserveAspectRatio=True,
                mask="auto"
            )

            y -= (img_height + 0.7 * cm)

        except Exception as e:
            c.setFont("Helvetica", 9)
            c.drawString(2 * cm, y, f"(Error mapa: {str(e)})")
            y -= 0.6 * cm

    # -------------------------
    # FOOTER NUEVO
    # -------------------------
    c.setFont("Helvetica", 9)
    c.drawString(
        2 * cm,
        2.2 * cm,
        "Cotización referencial. Puede variar por desvíos, esperas o condiciones operacionales."
    )
    c.drawString(
        2 * cm,
        1.7 * cm,
        "Para confirmar disponibilidad y reserva, contactar con al menos 3 días hábiles de anticipación al número +569 97799101."
    )

    c.save()

    if not os.path.exists(output_path):
        raise Exception("No se creó el PDF en disco")

    return output_path
