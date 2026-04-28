# pricing_engine.py

# Capacidades referenciales
CAPACIDADES = {
    "van": 15,
    "taxibus": 30,
    "bus": 45
}

# Parámetros nueva lógica pricing
PRECIO_DIESEL = 1450
FACTOR_COMERCIAL = 3.7

RENDIMIENTO_KM_LITRO = {
    "van": 6,
    "taxibus": 2.9,
    "bus": 2.9
}


def vehiculo_por_pasajeros(pasajeros: int) -> str:
    """
    <=15 van
    <=30 taxibus
    >30 bus
    """
    if pasajeros <= 15:
        return "van"
    elif pasajeros <= 30:
        return "taxibus"
    else:
        return "bus"


def _calcular_precio_base_km(km_total: float, vehiculo: str) -> float:
    """
    Nueva lógica:
    - Bus / Taxibus: ((km_total / 2.9) * 1450 * 3.7)
    - Van: ((km_total / 6) * 1450 * 3.7)
    """

    if km_total <= 0:
        raise Exception("Kilómetros inválidos")

    if vehiculo not in RENDIMIENTO_KM_LITRO:
        raise Exception(f"Vehículo inválido: {vehiculo}")

    rendimiento = RENDIMIENTO_KM_LITRO[vehiculo]

    precio = (km_total / rendimiento) * PRECIO_DIESEL * FACTOR_COMERCIAL

    return precio


def calcular_precio(km_total: float, horas_total: float, pasajeros: int) -> dict:
    """
    Cotización de 1 solo vehículo.
    horas_total se mantiene como parámetro para no romper el resto del sistema,
    pero ya no se usa en el cálculo del precio.
    """

    if pasajeros <= 0:
        raise Exception("Pasajeros inválidos")

    vehiculo = vehiculo_por_pasajeros(pasajeros)

    precio_final = _calcular_precio_base_km(km_total, vehiculo)

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
    pasajeros_asignados: int
) -> dict:
    """
    Calcula precio para un tipo de vehículo específico usando la nueva lógica por km.
    """

    precio_final = _calcular_precio_base_km(km_total, vehiculo)

    return {
        "vehiculo": vehiculo,
        "pasajeros_asignados": pasajeros_asignados,
        "km_total": round(km_total, 2),
        "horas_total": round(horas_total, 2),
        "costo_base": round(precio_final),
        "utilidad": 0,
        "precio_final": round(precio_final),
    }


def calcular_cotizacion_flotilla(km_total: float, horas_total: float, pasajeros: int) -> dict:
    """
    Calcula cotización con 1 o más vehículos según cantidad de pasajeros.

    Nueva lógica de precio:
    - Bus / Taxibus: ((km_total / 2.9) * 1450 * 3.7)
    - Van: ((km_total / 8) * 1450 * 3.7)
    """

    if pasajeros <= 0:
        raise Exception("Pasajeros inválidos")

    items = []

    vehiculo_simple = vehiculo_por_pasajeros(pasajeros)

    if pasajeros <= CAPACIDADES[vehiculo_simple]:
        detalle = _calcular_precio_por_vehiculo(
            km_total,
            horas_total,
            vehiculo_simple,
            pasajeros
        )
        items.append(detalle)

    else:
        restantes = pasajeros

        while restantes > CAPACIDADES["bus"]:
            detalle = _calcular_precio_por_vehiculo(
                km_total,
                horas_total,
                "bus",
                CAPACIDADES["bus"]
            )
            items.append(detalle)
            restantes -= CAPACIDADES["bus"]

        if restantes > 0:
            if restantes <= CAPACIDADES["van"]:
                items.append(
                    _calcular_precio_por_vehiculo(
                        km_total,
                        horas_total,
                        "van",
                        restantes
                    )
                )
            elif restantes <= CAPACIDADES["taxibus"]:
                items.append(
                    _calcular_precio_por_vehiculo(
                        km_total,
                        horas_total,
                        "taxibus",
                        restantes
                    )
                )
            else:
                items.append(
                    _calcular_precio_por_vehiculo(
                        km_total,
                        horas_total,
                        "bus",
                        restantes
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
