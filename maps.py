import os
import requests
from urllib.parse import quote
import re
import difflib

from lugares_conocidos import LUGARES_CONOCIDOS
# from comunas_rm import COMUNAS_RM  # ⚠️ no se usa porque aquí se redefine

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
    s = (s or "").strip().lower()
    s = s.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    s = re.sub(r"[^\w\s]", " ", s)  # saca signos
    s = re.sub(r"\s+", " ", s)
    return s


def _contains_any(text: str, words: list[str]) -> bool:
    t = (text or "").lower()
    return any(w in t for w in words)
def _normalizar_key(txt: str) -> str:
    txt = (txt or "").strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt
def _tokens(txt: str) -> list[str]:
    return [t for t in _clean_text(txt).split() if t]


def _sim(a: str, b: str) -> float:
    # Similaridad tolerante a faltas de ortografía
    return difflib.SequenceMatcher(None, _clean_text(a), _clean_text(b)).ratio()


def _buscar_lugar_conocido_fuzzy(direccion: str):
    """
    Matching inteligente para lugares_conocidos:
    - Coincidencia exacta (normalizada)
    - Coincidencia por tokens (parcial)
    - Fuzzy match (errores ortográficos)
    Retorna (lat, lon, key_match, score) o None
    """
    d = _clean_text(direccion)

    if not d:
        return None

    # 1) exact match
    if d in LUGARES_CONOCIDOS:
        lat, lon = LUGARES_CONOCIDOS[d]
        return float(lat), float(lon), d, 1.0

    # Preparar tokens del input
    dtoks = set(_tokens(d))

    mejor = None  # (lat, lon, key, score)

    for k, coords in LUGARES_CONOCIDOS.items():
        k_norm = _clean_text(k)
        ktoks = set(_tokens(k_norm))

        score = 0.0

        # 2) match por contención (si escribió parte del nombre)
        if k_norm in d or d in k_norm:
            score += 0.85

        # 3) match por tokens (ej: "acupark" debería matchear "acuapark el idilio")
        if dtoks and ktoks:
            inter = len(dtoks.intersection(ktoks))
            union = len(dtoks.union(ktoks))
            jaccard = inter / union if union else 0.0
            score += (jaccard * 0.75)

        # 4) fuzzy para errores ortográficos (talGante / tlagante / talgante)
        score += (_sim(d, k_norm) * 0.90)

        # Penaliza matches muy débiles
        if score < 0.70:
            continue

        lat, lon = coords
        candidato = (float(lat), float(lon), k_norm, score)

        if (mejor is None) or (candidato[3] > mejor[3]):
            mejor = candidato

    return mejor


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

    # ✅ 0) PRIORIDAD: lugares conocidos con fuzzy matching
    hit = _buscar_lugar_conocido_fuzzy(direccion_original)
    if hit:
        lat, lon, k_match, score = hit
        print("📍 Geocode FORZADO (LUGAR CONOCIDO - FUZZY):", direccion_original, "=>", (lat, lon), "| match:", k_match, "| score:", round(score, 3))
        return lat, lon

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
        "proximity": "-70.6693,-33.4489",

        # ✅ Evita resultados fuera de Chile (bounding box Chile aprox)
        # [minLon, minLat, maxLon, maxLat]
        "bbox": "-75,-56,-66,-17",

        # ✅ Reduce resultados ambiguos (menos riesgo de lugares random)
        "types": "place,locality,neighborhood,address,poi"
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

    # ✅ Fail-safe: si sale fuera de Chile, rechazamos
    if not (-56 <= lat <= -17 and -75 <= lon <= -66):
        raise Exception(f"Geocoding fuera de Chile para '{direccion_original}': lat={lat}, lon={lon}, elegido={best.get('place_name')}")

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

