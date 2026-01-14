# geocoding/geocoding_resolver.py

import re
import requests
import os

from .lugares_conocidos import LUGARES_CONOCIDOS
from .comunas_rm import COMUNAS_RM

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")


def normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()

    reemplazos = {
        "av ": "avenida ",
        "av.": "avenida ",
        "stgo": "santiago",
        "rm": "region metropolitana",
        "metro ": "",
        "mall ": "mall ",
    }

    for k, v in reemplazos.items():
        texto = texto.replace(k, v)

    texto = re.sub(r"\s+", " ", texto)
    return texto


def geocode_mapbox(query: str):
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"

    params = {
        "access_token": MAPBOX_TOKEN,
        "country": "cl",
        "limit": 1,
        "types": "address,poi,place",
        "bbox": "-70.9,-33.8,-70.3,-33.2"  # Región Metropolitana
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    if not data.get("features"):
        raise ValueError("Mapbox sin resultados")

    lon, lat = data["features"][0]["center"]
    return lat, lon


def fallback_comuna(texto: str):
    for comuna, coords in COMUNAS_RM.items():
        if comuna in texto:
            return coords
    raise ValueError("No se encontró comuna")


def resolver_direccion(texto_original: str):
    if not texto_original or len(texto_original.strip()) < 3:
        raise ValueError("Dirección inválida")

    texto = normalizar_texto(texto_original)

    # 1️⃣ Diccionario interno
    if texto in LUGARES_CONOCIDOS:
        return LUGARES_CONOCIDOS[texto]

    # 2️⃣ Mapbox contextualizado a RM
    try:
        query = f"{texto}, region metropolitana, chile"
        return geocode_mapbox(query)
    except Exception:
        pass

    # 3️⃣ Fallback por comuna
    try:
        return fallback_comuna(texto)
    except Exception:
        pass

    # 4️⃣ Error controlado
    raise ValueError(f"No se pudo geocodificar: {texto_original}")
