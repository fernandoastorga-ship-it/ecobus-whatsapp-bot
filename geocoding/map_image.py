import os
import requests
from urllib.parse import quote


MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")


def generar_mapa_static(origen, destino, polyline: str) -> str:
    """
    Genera una imagen estática tipo mapa (PNG) con la ruta dibujada.
    Retorna la ruta del archivo generado.
    """

    if not MAPBOX_TOKEN:
        raise Exception("MAPBOX_TOKEN no está configurado")

    # ✅ style (puedes cambiarlo después)
    style = "mapbox/streets-v12"

    # ✅ Polyline debe ir URL-encoded
    encoded_polyline = quote(polyline)

    # Marcadores origen/destino (lon,lat)
    lon_o, lat_o = origen[1], origen[0]
    lon_d, lat_d = destino[1], destino[0]

    # Línea (route) + markers
    # Nota: path-5+00aa88-0.7(...) -> ruta verde
    overlays = (
        f"path-5+00aa88-0.7({encoded_polyline}),"
        f"pin-s-a+000000({lon_o},{lat_o}),"
        f"pin-s-b+000000({lon_d},{lat_d})"
    )

    # auto = centra y ajusta zoom automático
    url = f"https://api.mapbox.com/styles/v1/{style}/static/{overlays}/auto/900x500"

    params = {
        "access_token": MAPBOX_TOKEN
    }

    r = requests.get(url, params=params, timeout=20)

    if r.status_code != 200:
        raise Exception(f"Mapbox Static Image error {r.status_code}: {r.text}")

    output_path = f"/tmp/mapa_ruta.png"

    with open(output_path, "wb") as f:
        f.write(r.content)

    return output_path
