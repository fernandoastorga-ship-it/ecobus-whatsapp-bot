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
import os
import requests
from urllib.parse import quote

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")
ORS_API_KEY = os.getenv("ORS_API_KEY")


# ✅ Diccionario de comunas / lugares típicos RM para “forzar contexto”
RM_HINTS = [
    "peñaflor", "penaflor",
    "isla de maipo",
    "talagante",
    "padre hurtado",
    "curacaví", "curacavi",
    "melipilla",
    "maipú", "maipu",
    "pudahuel",
    "estación central", "estacion central",
    "santiago",
    "cerrillos",
    "el monte"
]

# ✅ Lugares típicos V Región para no confundir con “Santiago”
V_HINTS = [
    "viña", "vina", "viña del mar", "vina del mar",
    "valpara", "valparaíso", "valparaiso",
    "quilpué", "quilpue",
    "villa alemana",
    "concón", "concon",
    "reñaca", "renaca",
    "casablanca"
]


def _contains_any(text: str, words: list[str]) -> bool:
    t = (text or "").lower()
    return any(w in t for w in words)


def geocode(direccion: str):
    """
    Geocoding robusto Chile.
    - URL encode
    - country=CL
    - proximity Santiago
    - scoring por comuna / región
    - evita POI incorrectos (ej: Pasaje Peñaflor en Estación Central)
    """

    if not MAPBOX_TOKEN:
        raise Exception("MAPBOX_TOKEN no está definido en variables de entorno")

    direccion_original = direccion
    direccion = (direccion or "").strip()

    if not direccion:
        raise Exception("Dirección vacía")

    # ✅ Si el usuario escribe solo “Peñaflor”, es mejor ayudar al geocoder con “Chile”
    # (esto reduce MUCHÍSIMO errores de lugares “parecidos”)
    direccion_expandida = direccion
    if len(direccion.split()) <= 2:
        direccion_expandida = f"{direccion}, Chile"

    # ✅ Sesgo RM si detectamos comunas RM
    # (esto NO bloquea Viña/Valpo, porque tiene su propio hint)
    texto_lower = direccion.lower()
    es_rm = _contains_any(texto_lower, RM_HINTS)
    es_quinta = _contains_any(texto_lower, V_HINTS)

    # ✅ URL encoding
    direccion_q = quote(direccion_expandida)

    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{direccion_q}.json"
    params = {
        "access_token": MAPBOX_TOKEN,
        "country": "CL",
        "limit": 8,             # más candidatos para filtrar bien
        "language": "es",
        "autocomplete": "true",
        # Sesgo a Santiago (lon,lat)
        "proximity": "-70.6693,-33.4489"
    }

    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    features = data.get("features", [])
    if not features:
        raise Exception(f"No se pudo geocodificar: {direccion_original}")

    # ✅ Filtrar tipos útiles
    tipos_permitidos = {"place", "locality", "address", "poi", "neighborhood"}
    candidatos = [f for f in features if any(t in tipos_permitidos for t in f.get("place_type", []))]
    if not candidatos:
        candidatos = features

    def score_feature(f):
        relevance = float(f.get("relevance", 0))
        place_name = (f.get("place_name") or "").lower()
        place_type = f.get("place_type", [])

        bonus = 0.0

        # ✅ Si el input menciona Quinta Región, bonifica Quinta Región
        if es_quinta:
            if _contains_any(place_name, V_HINTS):
                bonus += 1.0
            # Penaliza Santiago/RM si estamos buscando quinta región
            if "santiago" in place_name or "región metropolitana" in place_name or "region metropolitana" in place_name:
                bonus -= 0.8

        # ✅ Si el input menciona RM, bonifica RM
        if es_rm and not es_quinta:
            if "región metropolitana" in place_name or "region metropolitana" in place_name or "santiago" in place_name:
                bonus += 0.8

        # ✅ Si input es una comuna, el mejor match suele ser "place/locality"
        if "place" in place_type:
            bonus += 0.45
        if "locality" in place_type:
            bonus += 0.35

        # ✅ POI (malls/aeropuertos) son OK, pero no deben ganarle a una comuna real
        if "poi" in place_type:
            bonus += 0.10
        if "address" in place_type:
            bonus += 0.15

        # ✅ Penalizar "Pasaje X" si el input era solo "X" (ej: Peñaflor)
        # porque Mapbox a veces sugiere calles o pasajes con ese nombre.
        if len(direccion.split()) <= 2:
            if "pasaje" in place_name or "calle" in place_name or "avenida" in place_name:
                bonus -= 0.7

        # ✅ Bonus fuerte si contiene exactamente el texto del usuario
        if direccion.lower() in place_name:
            bonus += 0.6

        return relevance + bonus

    candidatos.sort(key=score_feature, reverse=True)
    best = candidatos[0]

    # ✅ Debug útil
    try:
        print("📍 Entrada geocode:", direccion_original)
        print("📍 Expandida:", direccion_expandida)
        print("📍 Geocode elegido:", best.get("place_name"))
    except:
        pass

    lon, lat = best["center"]
    return lat, lon


def route(origen, destino):
    if not ORS_API_KEY:
        raise Exception("ORS_API_KEY no está definido en variables de entorno")

    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }

    body = {
        "coordinates": [
            [origen[1], origen[0]],   # ORS: [lon, lat]
            [destino[1], destino[0]]
        ]
    }

    r = requests.post(url, json=body, headers=headers, timeout=30)
    data = r.json()

    if r.status_code >= 300:
        raise Exception(f"ORS error HTTP {r.status_code}: {data}")

    if "routes" not in data or not data["routes"]:
        raise Exception(f"No se pudo calcular la ruta (ORS): {data}")

    summary = data["routes"][0]["summary"]
    km = summary["distance"] / 1000
    horas = summary["duration"] / 3600

    polyline = data["routes"][0].get("geometry", "")

    return km, horas, polyline
