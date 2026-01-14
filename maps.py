# maps.py
import os
import requests

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

def geocode(direccion: str):
    url = "https://api.mapbox.com/geocoding/v5/mapbox.places/" + direccion + ".json"
    params = {
        "access_token": MAPBOX_TOKEN,
        "country": "CL",
        "limit": 1,
        "language": "es"
    }

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
        ]
    }

    r = requests.post(url, json=body, headers=headers, timeout=20)
    data = r.json()

    if "routes" not in data:
        raise Exception("No se pudo calcular la ruta")

    summary = data["routes"][0]["summary"]
    km = summary["distance"] / 1000
    horas = summary["duration"] / 3600

    return km, horas
