import os
import requests
import time

APP_ID = os.environ.get("APP_ID")
APP_SECRET = os.environ.get("APP_SECRET")

def refresh_access_token():
    url = "https://graph.facebook.com/v18.0/oauth/access_token"
    params = {
        "grant_type": "client_credentials",
        "client_id": APP_ID,
        "client_secret": APP_SECRET
    }

    try:
        response = requests.get(url, params=params).json()
        token = response.get("access_token")

        if token:
            # Guardar token en Variables de Entorno de Render dinámicamente
            os.environ["WHATSAPP_TOKEN"] = token
            print(f"🔄 Token actualizado correctamente: {token[:20]}...")
        else:
            print("❌ No se obtuvo token:", response)

    except Exception as e:
        print("❌ Error al actualizar token:", e)

if __name__ == "__main__":
    print("⏳ Sistema de actualización automática iniciado...")
    while True:
        refresh_access_token()
        time.sleep(6 * 60 * 60)  # Se ejecuta cada 6 horas
