import os
import requests
from urllib.parse import quote

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")
ORS_API_KEY = os.getenv("ORS_API_KEY")

def geocode(direccion: str):
    if not MAPBOX_TOKEN:
        raise Exception("MAPBOX_TOKEN no está definido en variables de entorno")

    direccion_original = direccion
    direccion = direccion.strip()

    if not direccion:
        raise Exception("Dirección vacía")

    direccion_q = quote(direccion)

    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{direccion_q}.json"
    params = {
        "access_token": MAPBOX_TOKEN,
        "country": "CL",
        "limit": 5,
        "language": "es",
        "autocomplete": "true",
        "proximity": "-70.6693,-33.4489"
    }

    r = requests.get(url, params=params, timeout=15)
    data = r.json()

    features = data.get("features", [])
    if not features:
        raise Exception(f"No se pudo geocodificar: {direccion_original}")

    # ✅ Filtrar tipos útiles para transporte (evita resultados raros)
    tipos_permitidos = {"poi", "address", "place", "locality", "neighborhood"}
    candidatos = [f for f in features if any(t in tipos_permitidos for t in f.get("place_type", []))]

    if not candidatos:
        candidatos = features

    # ✅ Heurística: si menciona lugares de V Región, prioriza esos
    texto_lower = direccion.lower()
    es_quinta = any(k in texto_lower for k in ["viña", "vina", "valpara", "quilpu", "villa alemana", "concon", "concón", "reñaca", "renaca"])

    def score_feature(f):
        # relevance suele venir de 0 a 1
        relevance = float(f.get("relevance", 0))

        place_name = (f.get("place_name") or "").lower()

        # Bonus por coincidencias semánticas de región
        bonus = 0.0

        if es_quinta:
            if any(k in place_name for k in ["viña", "vina del mar", "valpara", "valparaíso", "quilpu", "villa alemana", "concon", "concón"]):
                bonus += 0.6
        else:
            # Si NO es quinta región, sesga a RM
            if any(k in place_name for k in ["santiago", "región metropolitana", "region metropolitana"]):
                bonus += 0.4

        # Bonus por POI (malls/terminales/aeropuertos suelen estar como poi)
        place_type = f.get("place_type", [])
        if "poi" in place_type:
            bonus += 0.25
        if "address" in place_type:
            bonus += 0.20

        return relevance + bonus

    candidatos.sort(key=score_feature, reverse=True)

    # ✅ Escoge el mejor candidato según scoring
    best = candidatos[0]

    # Debug útil para Render logs (puedes dejarlo)
    try:
        print("📍 Geocode input:", direccion_original)
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

    # ✅ Si ORS responde error, muéstralo
    if r.status_code >= 300:
        raise Exception(f"ORS error HTTP {r.status_code}: {data}")

    if "routes" not in data or not data["routes"]:
        # ORS suele mandar 'error'/'message' cuando falla
        raise Exception(f"No se pudo calcular la ruta (ORS): {data}")

    summary = data["routes"][0]["summary"]
    km = summary["distance"] / 1000
    horas = summary["duration"] / 3600

    polyline = data["routes"][0].get("geometry", "")

    return km, horas, polyline


