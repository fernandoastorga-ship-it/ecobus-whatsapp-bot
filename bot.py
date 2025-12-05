def procesar_flujo(to, texto, texto_lower):
    u = usuarios[to]

    # 1) Nombre
    if u["estado"] == "nombre":
        u["Nombre"] = texto
        u["estado"] = "correo"
        enviar_texto(to, "📧 ¿Cuál es tu correo de contacto?")

    # 2) Correo (validación)
    elif u["estado"] == "correo":
        if not email_valido(texto):
            enviar_texto(to, "⚠️ Correo inválido. Ej: cliente@empresa.cl\nIntenta nuevamente:")
            return
        u["Correo"] = texto
        u["estado"] = "pasajeros"
        enviar_texto(to, "👥 ¿Cuántos pasajeros serán?")

    # 3) Pasajeros
    elif u["estado"] == "pasajeros":
        u["Pasajeros"] = texto
        u["estado"] = "fecha_viaje"
        enviar_texto(to, "📅 Fecha viaje (DD-MM-AAAA)")

    # 4) Validar fecha
    elif u["estado"] == "fecha_viaje":
        try:
            fecha = datetime.strptime(texto, "%d-%m-%Y").date()
            if fecha < date.today():
                enviar_texto(to, "⚠️ Fecha pasada. Ingrésala nuevamente:")
                return
            u["Fecha Viaje"] = fecha.strftime("%d-%m-%Y")
            u["estado"] = "origen"
            enviar_texto(to, "📍 Dirección de origen:")
        except ValueError:
            enviar_texto(to, "⚠️ Formato incorrecto. Ej: 25-12-2025")
            return

    # 5) Origen
    elif u["estado"] == "origen":
        u["Origen"] = texto
        u["estado"] = "destino"
        enviar_texto(to, "📍 Dirección de destino:")

    # 6) Destino
    elif u["estado"] == "destino":
        u["Destino"] = texto
        u["estado"] = "hora_ida"
        enviar_texto(to, "🕒 Hora Ida (HH:MM)")

    # 7) Validar hora ida
    elif u["estado"] == "hora_ida":
        if not hora_valida(texto):
            enviar_texto(to, "⚠️ Hora inválida. Ej: 07:45")
            return
        u["Hora Ida"] = texto
        u["estado"] = "hora_vuelta"
        enviar_texto(to, "🕒 Hora Regreso (HH:MM)")

    # 8) Validar hora regreso
    elif u["estado"] == "hora_vuelta":
        if not hora_valida(texto):
            enviar_texto(to, "⚠️ Hora inválida. Ej: 18:00")
            return
        u["Hora Regreso"] = texto
        u["estado"] = "telefono"
        enviar_texto(to, "📱 Teléfono de contacto:")

    # 9) Número
    elif u["estado"] == "telefono":
        u["Telefono"] = texto
        u["estado"] = "confirmar"
        mostrar_resumen(to)
        enviar_confirmacion(to)

    # 10) Confirmar
    elif u["estado"] == "confirmar":
        if texto_lower in ["si", "sí", "confirmar_si"]:

            enviar_texto(to,
                "🎉 *¡Solicitud recibida exitosamente!*\n"
                "Estamos preparando tu cotización 🚍\n"
                "📧 Revisa tu correo, ahí te llegará la información.\n"
                "Un ejecutivo te contactará pronto 🙌"
            )

            try:
                sheet.append_row([
                    datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    u['Nombre'], u['Correo'], u['Pasajeros'],
                    u['Fecha Viaje'], u['Origen'], u['Destino'],
                    u['Hora Ida'], u['Hora Regreso'], u['Telefono']
                ])
            except Exception as e:
                print("❌ Error guardando en Google Sheets:", e)

            enviar_correo_notificacion(u)
            usuarios.pop(to)
            menu_principal(to)

        else:
            enviar_texto(to, "👌 Puedes corregir lo que necesites.\nVolvamos al inicio 🚍")
            usuarios.pop(to)
            menu_principal(to)

