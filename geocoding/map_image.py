import os
import requests
from urllib.parse import quote

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")


def generar_mapa_static(origen, destino, polyline: str) -> str:
    """
    Genera imagen PNG con ruta y marcadores A/B.
    Guarda en /tmp y retorna el path.
    """

    if not MAPBOX_TOKEN:
        raise Exception("MAPBOX_TOKEN no está configurado")

    style = "mapbox/streets-v12"

    encoded_polyline = quote(polyline)

    lon_o, lat_o = origen[1], origen[0]
    lon_d, lat_d = destino[1], destino[0]

    overlays = (
        f"path-5+00aa88-0.7({encoded_polyline}),"
        f"pin-s-a+000000({lon_o},{lat_o}),"
        f"pin-s-b+000000({lon_d},{lat_d})"
    )

    url = f"https://api.mapbox.com/styles/v1/{style}/static/{overlays}/auto/900x500"
    params = {"access_token": MAPBOX_TOKEN}

    r = requests.get(url, params=params, timeout=20)

    if r.status_code != 200:
        raise Exception(f"Mapbox Static Image error {r.status_code}: {r.text}")

    output_path = "/tmp/mapa_ruta.png"

    with open(output_path, "wb") as f:
        f.write(r.content)

    return output_path

