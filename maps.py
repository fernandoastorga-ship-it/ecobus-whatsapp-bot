import os
import requests

# ===============================
# CONFIG
# ===============================
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")
ORS_API_KEY = os.getenv("ORS_API_KEY")

if not MAPBOX_TOKEN:
    raise RuntimeError("❌ MAPBOX_TOKEN no está definido en variables de entorno")

if not ORS_API_KEY:
    raise RuntimeError("❌ ORS_API_KEY no está definido en variables de entorno")


# ===============================
# NORMALIZACIÓN DE DIRECCIONES
# ===============================
def normalizar_direccion(texto: str) -> str:
    texto = texto.lower().strip()

    reemplazos = [
        "mall",
        "centro comercial",
        "shopping",
    ]

    for r in reemplazos:
        texto = texto.replace(r, "")

    while "  " in texto:
        texto = texto.replace("  ", " ")

    return texto


# ===============================
# GEOCODING (MAPBOX)
# ===============================
def geocode(direccion: str):
    direccion_original = direccion
    direccion = normalizar_direccion(direccion)

    print("🧭 Geocoding:", direccion_original)

    # Fallbacks progresivos (misma lógica, más robusta)
    queries = [
        direccion,
        f"{direccion}, Santiago",
        f"{direccion}, Región Metropolitana, Chile"
    ]

    for q in queries:
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{q}.json"
        params = {
            "access_token": MAPBOX_TOKEN,
            "country": "cl",
            "language": "es",
            "limit": 1,
            "types": "poi,address",
            # Bounding box Región Metropolitana
            "bbox": "-71.6,-33.7,-70.3,-33.2"
        }

        r = requests.get(url, params=params, timeout=10)
        print("📦 Mapbox geocode:", r.status_code, q)

        if r.status_code != 200:
            continue

        data = r.json()
        features = data.get("features", [])

        if features:
            lon, lat = features[0]["center"]
            return lat, lon

    raise Exception(f"No se pudo geocodificar: {direccion_original}")


# ===============================
# RUTEO (OPENROUTESERVICE)
# ===============================
def route(origen, destino):
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

    r = requests.post(url, json=body, headers=headers, timeout=20)

    if r.status_code != 200:
        raise Exception("No se pudo calcular la ruta")

    data = r.json()

    if "routes" not in data:
        raise Exception("No se pudo calcular la ruta")

    summary = data["routes"][0]["summary"]
    km = summary["distance"] / 1000
    horas = summary["duration"] / 3600

    return km, horas
