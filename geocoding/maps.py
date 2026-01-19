import os
import requests

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

def normalizar_direccion(texto: str) -> str:
    return texto.lower().strip()


def debe_usar_bbox_rm(query: str) -> bool:
    q = normalizar_direccion(query)

    # Si es un destino fuera de RM, NO forzar bbox RM
    palabras_fuera_rm = [
        "viña", "viña del mar",
        "valparaiso", "valparaíso",
        "quilpue", "quilpué",
        "villa alemana",
        "concon", "concón",
        "san antonio",
        "rancagua",
        "curico", "curicó",
        "talca",
        "chillan", "chillán",
        "concepcion", "concepción",
        "la serena",
        "coquimbo",
        "puerto montt",
        "temuco",
    ]
    for p in palabras_fuera_rm:
        if p in q:
            return False

    # Si es algo muy típico de RM o ambiguo, sí conviene bbox RM
    palabras_ambiguas = ["costanera", "mall", "metro", "terminal", "plaza", "santiago"]
    for p in palabras_ambiguas:
        if p in q:
            return True

    # Default: NO forzar bbox
    return False


def geocode(direccion: str):
    url = "https://api.mapbox.com/geocoding/v5/mapbox.places/" + direccion + ".json"

    params = {
        "access_token": MAPBOX_TOKEN,
        "country": "CL",
        "limit": 1,
        "language": "es"
    }

    # ✅ Cambio mínimo: bbox RM solo cuando corresponde
    if debe_usar_bbox_rm(direccion):
        params["bbox"] = "-71.6,-33.7,-70.3,-33.2"

    r = requests.get(url, params=params, timeout=10)
    data = r.json()

    if not data.get("features"):
        raise Exception(f"No se pudo geocodificar: {direccion}")

    lon, lat = data["features"][0]["center"]
    return lat, lon


def route(origen, destino):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        "Authorization": os.getenv("ORS_API_KEY"),
        "Content-Type": "application/json"
    }

    body = {
        "coordinates": [
            [origen[1], origen[0]],
            [destino[1], destino[0]]
        ],
        "geometry": True
    }

    r = requests.post(url, json=body, headers=headers, timeout=20)
    data = r.json()

    if "routes" not in data:
        raise Exception("No se pudo calcular la ruta")

    summary = data["routes"][0]["summary"]
    km = summary["distance"] / 1000
    horas = summary["duration"] / 3600

    polyline = data["routes"][0].get("geometry", "")

    return km, horas, polyline


