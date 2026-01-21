import os
import requests
from urllib.parse import quote

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")
ORS_API_KEY = os.getenv("ORS_API_KEY")


# ✅ Centros aproximados de comunas (RM)
# Esto evita errores tipo "Pasaje Peñaflor en Estación Central"
COMUNAS_RM = {
    "peñaflor": (-33.6169, -70.8764),
    "penaflor": (-33.6169, -70.8764),
    "isla de maipo": (-33.7491, -70.8975),
    "talagante": (-33.6669, -70.9304),
    "padre hurtado": (-33.5752, -70.8216),
    "el monte": (-33.6857, -70.9830),
    "melipilla": (-33.6894, -71.2158),
    "maipú": (-33.5095, -70.7576),
    "maipu": (-33.5095, -70.7576),
}


# ✅ Lugares típicos V Región (solo ayuda en scoring)
V_HINTS = [
    "viña", "vina", "viña del mar", "vina del mar",
    "valpara", "valparaíso", "valparaiso",
    "quilpué", "quilpue",
    "villa alemana",
    "concón", "concon",
    "reñaca", "renaca",
    "casablanca"
]


def _clean_text(s: str) -> str:
    return (s or "").strip().lower()


def _contains_any(text: str, words: list[str]) -> bool:
    t = (text or "").lower()
    return any(w in t for w in words)


def geocode(direccion: str):
    """
    Geocoding robusto Chile:
    1) Si es comuna RM conocida -> retorna coords fijas
    2) Si no -> fallback Mapbox con filtros/scoring
    """

    if not direccion:
        raise Exception("Dirección vacía")

    direccion_original = direccion
    d = _clean_text(direccion)

    # ✅ 1) FORZAR comunas RM conocidas (tu caso crítico)
    if d in COMUNAS_RM:
        lat, lon = COMUNAS_RM[d]
        print("📍 Geocode FORZADO (RM):", direccion_original, "=>", (lat, lon))
        return lat, lon

    # ✅ 2) Fallback Mapbox
    if not MAPBOX_TOKEN:
        raise Exception("MAPBOX_TOKEN no está definido en variables de entorno")

    # Ayuda si es muy corto
    direccion_expandida = direccion.strip()
    if len(direccion_expandida.split()) <= 2:
        direccion_expandida = f"{direccion_expandida}, Chile"

    direccion_q = quote(direccion_expandida)

    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{direccion_q}.json"
    params = {
        "access_token": MAPBOX_TOKEN,
        "country": "CL",
        "limit": 8,
        "language": "es",
        "autocomplete": "true",
        "proximity": "-70.6693,-33.4489"
    }

    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    features = data.get("features", [])
    if not features:
        raise Exception(f"No se pudo geocodificar: {direccion_original}")

    tipos_permitidos = {"place", "locality", "address", "poi", "neighborhood"}
    candidatos = [f for f in features if any(t in tipos_permitidos for t in f.get("place_type", []))]
    if not candidatos:
        candidatos = features

    texto_lower = d
    es_quinta = _contains_any(texto_lower, V_HINTS)

    def score_feature(f):
        relevance = float(f.get("relevance", 0))
        place_name = (f.get("place_name") or "").lower()
        place_type = f.get("place_type", [])

        bonus = 0.0

        if es_quinta:
            if _contains_any(place_name, V_HINTS):
                bonus += 1.0
            if "santiago" in place_name or "región metropolitana" in place_name or "region metropolitana" in place_name:
                bonus -= 0.8

        # comuna -> preferir place/locality
        if "place" in place_type:
            bonus += 0.45
        if "locality" in place_type:
            bonus += 0.35

        # address / poi ok pero no dominan
        if "address" in place_type:
            bonus += 0.15
        if "poi" in place_type:
            bonus += 0.10

        # penaliza “Pasaje/Calle/Avenida” si el input era muy corto
        if len(direccion.strip().split()) <= 2:
            if "pasaje" in place_name or "calle" in place_name or "avenida" in place_name:
                bonus -= 0.7

        if d in place_name:
            bonus += 0.6

        return relevance + bonus

    candidatos.sort(key=score_feature, reverse=True)
    best = candidatos[0]

    print("📍 Entrada geocode:", direccion_original)
    print("📍 Expandida:", direccion_expandida)
    print("📍 Geocode elegido:", best.get("place_name"))

    lon, lat = best["center"]
    return lat, lon


def route(origen, destino):
    """
    Retorna: (km, horas, polyline)
    """
    if not ORS_API_KEY:
        raise Exception("ORS_API_KEY no está definido en variables de entorno")

    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }

    body = {
        "coordinates": [
            [origen[1], origen[0]],
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

