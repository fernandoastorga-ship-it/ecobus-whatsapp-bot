from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from datetime import datetime


def generar_pdf_cotizacion(usuario: dict) -> str:
    """
    Genera un PDF con la cotización formal.
    Retorna la ruta del archivo generado.
    """

    cot_id = usuario.get("cotizacion_id", "SINID")
    filename = f"cotizacion_{cot_id}.pdf"

    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Título
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2 * cm, height - 2.5 * cm, "COTIZACIÓN DE TRANSPORTE - ECOBUS")

    # Subtítulo
    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, height - 3.3 * cm, f"Fecha emisión: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    c.drawString(2 * cm, height - 3.9 * cm, f"ID Cotización: {cot_id}")

    # Datos del cliente
    y = height - 5.2 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Datos del solicitante")
    y -= 0.6 * cm

    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y, f"Nombre: {usuario.get('Nombre', '')}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Correo: {usuario.get('Correo', '')}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Teléfono: {usuario.get('Telefono', '')}")

    # Datos del viaje
    y -= 1.0 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Detalle del viaje")
    y -= 0.6 * cm

    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y, f"Fecha viaje: {usuario.get('Fecha Viaje', '')}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Pasajeros: {usuario.get('Pasajeros', '')}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Origen: {usuario.get('Origen', '')}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Destino: {usuario.get('Destino', '')}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Horario: {usuario.get('Hora Ida', '')} - {usuario.get('Hora Regreso', '')}")

    # Resultado calculado
    y -= 1.0 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Estimación automática")
    y -= 0.6 * cm

    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y, f"Vehículo sugerido: {usuario.get('Vehiculo', '')}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"KM estimados (total): {usuario.get('KM Total', '')}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Horas estimadas (total): {usuario.get('Horas Total', '')}")
    y -= 0.5 * cm

    precio = usuario.get("Precio", "")
    c.setFont("Helvetica-Bold", 13)
    c.drawString(2 * cm, y, f"TOTAL ESTIMADO: ${precio}")

    # Texto informativo final
    y -= 1.3 * cm
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, "Esta cotización es referencial y puede variar según desvíos, esperas o condiciones operacionales.")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, "Para confirmar disponibilidad y reserva, responda este correo o contáctenos por WhatsApp.")

    # Pie
    y -= 1.2 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, "Ecobus / Ecovan - Transporte privado de pasajeros")

    c.save()
    return filename
