# pricing_engine.py

COSTOS = {
    "van": {"km": 904, "hora": 13080},
    "taxibus": {"km": 1264, "hora": 13080},
    "bus": {"km": 1190, "hora": 13080},
}

MARGEN = 0.35  # 35%

def vehiculo_por_pasajeros(pasajeros: int) -> str:
    if pasajeros <= 15:
        return "van"
    elif pasajeros <= 30:
        return "taxibus"
    else:
        return "bus"


def calcular_precio(km_total: float, horas_total: float, pasajeros: int) -> dict:
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
