# pricing_engine.py

COSTOS = {
    "van": {"km": 904, "hora": 13080},
    "taxibus": {"km": 1264, "hora": 13080},
    "bus": {"km": 1190, "hora": 13080},
}

MARGEN = 0.40  # 40%

# Capacidades referenciales (puedes ajustarlas si tu flota real cambia)
CAPACIDADES = {
    "van": 15,
    "taxibus": 30,
    "bus": 45
}


def vehiculo_por_pasajeros(pasajeros: int) -> str:
    """
    Lógica simple (la que ya tenías):
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


def calcular_precio(km_total: float, horas_total: float, pasajeros: int) -> dict:
    """
    Cotización de 1 solo vehículo (tu lógica actual).
    """
    vehiculo = vehiculo_por_pasajeros(pasajeros)
    costos = COSTOS[vehiculo]

    costo_base = (km_total * costos["km"]) + (horas_total * costos["hora"])
    utilidad = costo_base * MARGEN
    precio_final = costo_base + utilidad

    return {
        "vehiculo": vehiculo,
        "km_total": round(km_total, 2),
        "horas_total": round(horas_total, 2),
        "costo_base": round(costo_base),
        "utilidad": round(utilidad),
        "precio_final": round(precio_final),
    }


def _calcular_precio_por_vehiculo(km_total: float, horas_total: float, vehiculo: str, pasajeros_asignados: int) -> dict:
    """
    Calcula precio para un tipo de vehículo específico.
    """
    costos = COSTOS[vehiculo]

    costo_base = (km_total * costos["km"]) + (horas_total * costos["hora"])
    utilidad = costo_base * MARGEN
    precio_final = costo_base + utilidad

    return {
        "vehiculo": vehiculo,
        "pasajeros_asignados": pasajeros_asignados,
        "km_total": round(km_total, 2),
        "horas_total": round(horas_total, 2),
        "costo_base": round(costo_base),
        "utilidad": round(utilidad),
        "precio_final": round(precio_final),
    }


def calcular_cotizacion_flotilla(km_total: float, horas_total: float, pasajeros: int) -> dict:
    """
    NUEVO: Calcula una cotización con 1 o más vehículos, según cantidad de pasajeros.

    Regla de negocio que tú pediste:
    - Si son pocos pasajeros -> 1 vehículo lógico (van/taxibus/bus)
    - Si se pasa la capacidad -> se asigna más de 1 vehículo
    - Evitar sugerencias absurdas como "2 vans de 15 para 30" si un taxibus/bus lo resuelve mejor
    - Ejemplo esperado: 50 pax => bus (45) + van (5)
    """

    if pasajeros <= 0:
        raise Exception("Pasajeros inválidos")

    items = []

    # Caso simple: cabe en 1 vehículo usando tu lógica
    vehiculo_simple = vehiculo_por_pasajeros(pasajeros)

    # Si cabe dentro de su capacidad, cotiza 1 solo
    if pasajeros <= CAPACIDADES[vehiculo_simple]:
        detalle = _calcular_precio_por_vehiculo(km_total, horas_total, vehiculo_simple, pasajeros)
        items.append(detalle)

    else:
        # Si excede, empezamos llenando buses (45) porque es lo más eficiente para muchos pasajeros
        restantes = pasajeros

        # 1) Llenar buses de 45
        while restantes > CAPACIDADES["bus"]:
            detalle = _calcular_precio_por_vehiculo(km_total, horas_total, "bus", CAPACIDADES["bus"])
            items.append(detalle)
            restantes -= CAPACIDADES["bus"]

        # 2) Resolver el restante con el vehículo "más lógico"
        # Preferencias para evitar configuraciones raras
        # - Si restante <= 15 -> van
        # - Si restante <= 30 -> taxibus (mejor que 2 vans)
        # - Si restante > 30 -> bus
        if restantes > 0:
            if restantes <= CAPACIDADES["van"]:
                items.append(_calcular_precio_por_vehiculo(km_total, horas_total, "van", restantes))
            elif restantes <= CAPACIDADES["taxibus"]:
                items.append(_calcular_precio_por_vehiculo(km_total, horas_total, "taxibus", restantes))
            else:
                items.append(_calcular_precio_por_vehiculo(km_total, horas_total, "bus", restantes))

    # Totalizar
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
    Convierte items de flotilla a un resumen corto y claro.
    Ejemplos:
    - 2 buses => "2 buses (45 pax c/u)"
    - bus + van => "1 bus (45 pax c/u) + 1 van (15 pax c/u)"
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

    # Agrupar por tipo
    conteo = {}
    for it in items:
        v = it.get("vehiculo", "")
        conteo[v] = conteo.get(v, 0) + 1

    partes = []
    for v in ["bus", "taxibus", "van"]:  # orden lógico
        if v in conteo:
            n = conteo[v]
            cap = capacidades.get(v, "")
            partes.append(f"{n} {nombre_vehiculo(v, n)} ({cap} pax c/u)")

    return " + ".join(partes)

