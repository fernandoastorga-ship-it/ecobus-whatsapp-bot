# pricing_engine.py

# Capacidades referenciales
CAPACIDADES = {
    "van": 15,
    "taxibus": 30,
    "bus": 45
}

# Parámetros pricing
PRECIO_DIESEL = 1450
FACTOR_COMERCIAL = 3.7

RENDIMIENTO_KM_LITRO = {
    "van": 6,
    "taxibus": 2.9,
    "bus": 2.9
}

# Castigo interno para viajes cortos
KM_UMBRAL_CORTO = 100


def vehiculo_por_pasajeros(pasajeros: int) -> str:
    if pasajeros <= 15:
        return "van"
    elif pasajeros <= 30:
        return "taxibus"
    else:
        return "bus"


def _calcular_precio_base_km(
    km_total: float,
    vehiculo: str,
    km_base_origen: float = 0
) -> float:
    """
    Precio:
    - Van:      (km_tarifarios / 6) * 1450 * 3.7
    - Taxibus:  (km_tarifarios / 2.9) * 1450 * 3.7
    - Bus:      (km_tarifarios / 2.9) * 1450 * 3.7

    Si el viaje tiene menos de 100 km:
        km_tarifarios = km_total + km_base_origen

    IMPORTANTE:
    km_base_origen NO se muestra al cliente.
    Solo se usa para calcular precio.
    """

    if km_total <= 0:
        raise Exception("Kilómetros inválidos")

    if vehiculo not in RENDIMIENTO_KM_LITRO:
        raise Exception(f"Vehículo inválido: {vehiculo}")

    km_tarifarios = km_total

    # ✅ Castigo solo para viajes menores a 100 km
    # ✅ Suma SOLO UNA IDA: Peñaflor -> origen
    if km_total < KM_UMBRAL_CORTO and km_base_origen > 0:
        km_tarifarios = km_total + km_base_origen

    rendimiento = RENDIMIENTO_KM_LITRO[vehiculo]

    precio = (km_tarifarios / rendimiento) * PRECIO_DIESEL * FACTOR_COMERCIAL

    return precio


def calcular_precio(
    km_total: float,
    horas_total: float,
    pasajeros: int,
    km_base_origen: float = 0
) -> dict:
    """
    Cotización de 1 solo vehículo.

    horas_total se mantiene para no romper el bot,
    pero ya no se usa en el cálculo del precio.
    """

    if pasajeros <= 0:
        raise Exception("Pasajeros inválidos")

    vehiculo = vehiculo_por_pasajeros(pasajeros)

    precio_final = _calcular_precio_base_km(
        km_total=km_total,
        vehiculo=vehiculo,
        km_base_origen=km_base_origen
    )

    return {
        "vehiculo": vehiculo,
        "km_total": round(km_total, 2),
        "horas_total": round(horas_total, 2),
        "costo_base": round(precio_final),
        "utilidad": 0,
        "precio_final": round(precio_final),
    }


def _calcular_precio_por_vehiculo(
    km_total: float,
    horas_total: float,
    vehiculo: str,
    pasajeros_asignados: int,
    km_base_origen: float = 0
) -> dict:
    """
    Calcula precio para un tipo de vehículo específico.
    """

    precio_final = _calcular_precio_base_km(
        km_total=km_total,
        vehiculo=vehiculo,
        km_base_origen=km_base_origen
    )

    return {
        "vehiculo": vehiculo,
        "pasajeros_asignados": pasajeros_asignados,
        "km_total": round(km_total, 2),
        "horas_total": round(horas_total, 2),
        "costo_base": round(precio_final),
        "utilidad": 0,
        "precio_final": round(precio_final),
    }


def calcular_cotizacion_flotilla(
    km_total: float,
    horas_total: float,
    pasajeros: int,
    km_base_origen: float = 0
) -> dict:
    """
    Calcula cotización con 1 o más vehículos según cantidad de pasajeros.
    """

    if pasajeros <= 0:
        raise Exception("Pasajeros inválidos")

    items = []

    vehiculo_simple = vehiculo_por_pasajeros(pasajeros)

    if pasajeros <= CAPACIDADES[vehiculo_simple]:
        detalle = _calcular_precio_por_vehiculo(
            km_total=km_total,
            horas_total=horas_total,
            vehiculo=vehiculo_simple,
            pasajeros_asignados=pasajeros,
            km_base_origen=km_base_origen
        )
        items.append(detalle)

    else:
        restantes = pasajeros

        while restantes > CAPACIDADES["bus"]:
            detalle = _calcular_precio_por_vehiculo(
                km_total=km_total,
                horas_total=horas_total,
                vehiculo="bus",
                pasajeros_asignados=CAPACIDADES["bus"],
                km_base_origen=km_base_origen
            )
            items.append(detalle)
            restantes -= CAPACIDADES["bus"]

        if restantes > 0:
            if restantes <= CAPACIDADES["van"]:
                items.append(
                    _calcular_precio_por_vehiculo(
                        km_total=km_total,
                        horas_total=horas_total,
                        vehiculo="van",
                        pasajeros_asignados=restantes,
                        km_base_origen=km_base_origen
                    )
                )

            elif restantes <= CAPACIDADES["taxibus"]:
                items.append(
                    _calcular_precio_por_vehiculo(
                        km_total=km_total,
                        horas_total=horas_total,
                        vehiculo="taxibus",
                        pasajeros_asignados=restantes,
                        km_base_origen=km_base_origen
                    )
                )

            else:
                items.append(
                    _calcular_precio_por_vehiculo(
                        km_total=km_total,
                        horas_total=horas_total,
                        vehiculo="bus",
                        pasajeros_asignados=restantes,
                        km_base_origen=km_base_origen
                    )
                )

    total_costo_base = sum(x["costo_base"] for x in items)
    total_utilidad = sum(x["utilidad"] for x in items)
    total_precio_final = sum(x["precio_final"] for x in items)

    return {
        "pasajeros": pasajeros,
        "km_total": round(km_total, 2),
        "horas_total": round(horas_total, 2),
        "items": items,
        "costo_base_total": round(total_costo_base),
        "utilidad_total": round(total_utilidad),
        "precio_final_total": round(total_precio_final),
    }


def resumen_flotilla(items: list[dict]) -> str:
    """
    Convierte items de flotilla a un resumen corto.
    """

    if not items:
        return ""

    capacidades = {"van": 15, "taxibus": 30, "bus": 45}

    def nombre_vehiculo(v: str, n: int) -> str:
        if n == 1:
            return v
        if v == "bus":
            return "buses"
        return v + "s"

    conteo = {}

    for it in items:
        v = it.get("vehiculo", "")
        conteo[v] = conteo.get(v, 0) + 1

    partes = []

    for v in ["bus", "taxibus", "van"]:
        if v in conteo:
            n = conteo[v]
            cap = capacidades.get(v, "")
            partes.append(f"{n} {nombre_vehiculo(v, n)} ({cap} pax c/u)")

    return " + ".join(partes)
