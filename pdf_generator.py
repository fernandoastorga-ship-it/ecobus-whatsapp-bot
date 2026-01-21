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

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, height - 2.2 * cm, "COTIZACIÓN DE TRANSPORTE - ECOBUS")

    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, height - 2.9 * cm, f"Fecha emisión: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    c.drawString(2 * cm, height - 3.4 * cm, f"ID Cotización: {cot_id}")

    y = height - 4.5 * cm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Datos del solicitante")
    y -= 0.6 * cm

    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, f"Nombre: {usuario.get('Nombre', '')}")
    y -= 0.45 * cm
    c.drawString(2 * cm, y, f"Correo: {usuario.get('Correo', '')}")
    y -= 0.45 * cm
    c.drawString(2 * cm, y, f"Teléfono: {usuario.get('Telefono', '')}")

    y -= 0.8 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Detalle del viaje")
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

    y -= 0.8 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Estimación automática")
    y -= 0.6 * cm

    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, f"Vehículo sugerido: {usuario.get('Vehiculo', '')}")
    y -= 0.45 * cm
    km_txt = usuario.get("KM Total", "")
    horas_txt = usuario.get("Horas Total", "")


    if km_txt in ["", None]:
        km_txt = "PENDIENTE"
    if horas_txt in ["", None]:
        horas_txt = "PENDIENTE"

    c.drawString(2 * cm, y, f"KM estimados (total): {km_txt}")
    y -= 0.45 * cm
    c.drawString(2 * cm, y, f"Horas estimadas (total): {horas_txt}")

    y -= 0.45 * cm
    c.drawString(2 * cm, y, f"Horas estimadas (total): {usuario.get('Horas Total', '')}")
    y -= 0.65 * cm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, f"TOTAL ESTIMADO: ${usuario.get('Precio', '')}")

    # ✅ MAPA dentro del PDF
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
            c.drawString(2 * cm, y, f"(No se pudo renderizar el mapa en PDF: {str(e)})")
            y -= 0.6 * cm
    else:
        c.setFont("Helvetica", 9)
        c.drawString(2 * cm, y, "(Mapa no disponible para esta cotización)")
        y -= 0.6 * cm

    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, 2.2 * cm, "Cotización referencial. Puede variar por desvíos, esperas o condiciones operacionales.")
    c.drawString(2 * cm, 1.7 * cm, "Para confirmar disponibilidad y reserva, responda este correo.")

    c.save()

    if not os.path.exists(output_path):
        raise Exception("No se creó el PDF en disco")

    return output_path
