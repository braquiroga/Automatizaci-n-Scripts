import os
import requests
import json
from getpass import getpass
from dotenv import load_dotenv, set_key
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv(dotenv_path='.env')

def verify_unifi_credentials(url, username, password):
    """Verifica login contra UniFi."""
    try:
        session = requests.Session()
        data = {"username": username, "password": password}
        headers = {"Content-Type": "application/json"}
        r = session.post(f"{url}/api/login", data=json.dumps(data), headers=headers, verify=False)
        if r.status_code == 200:
            print("✅ Credenciales UniFi verificadas correctamente.")
            return session
        else:
            print("❌ Error al verificar credenciales UniFi.")
            return None
    except Exception as e:
        print(f"❌ Error al conectar con UniFi: {e}")
        return None

def list_unifi_sites(session, url):
    try:
        r = session.get(f"{url}/api/self/sites", verify=False)
        r.raise_for_status()
        sites = r.json()["data"]
        print("\n🌐 Sitios disponibles en UniFi:")
        for i, site in enumerate(sites):
            print(f"{i + 1}. {site['desc']} (ID: {site['name']})")
        return sites
    except Exception as e:
        print(f"❌ Error al listar sitios de UniFi: {e}")
        return []

def select_unifi_site(sites):
    while True:
        try:
            choice = int(input("Selecciona un sitio por número: ")) - 1
            if 0 <= choice < len(sites):
                return sites[choice]
            else:
                print("Selección inválida.")
        except ValueError:
            print("Por favor ingresa un número válido.")

def list_ssids(session, url, site_id):
    try:
        r = session.get(f"{url}/api/s/{site_id}/stat/device", verify=False)
        aps = r.json().get('data', [])
        ssids = set()
        for ap in aps:
            for vap in ap.get('vap_table', []):
                ssids.add(vap.get('essid', ''))
        return list(ssids)
    except Exception as e:
        print(f"❌ Error al listar SSIDs: {e}")
        return []

def configure_ssids_to_omit(ssids):
    while True:
        try:
            print("\nSelecciona los SSIDs que deseas omitir (separados por comas):")
            for i, ssid in enumerate(ssids):
                print(f"{i + 1}. {ssid}")
            choices = input("Introduce los números de los SSIDs a omitir (ej: 1,3): ").split(',')
            result = [ssids[int(c.strip()) - 1] for c in choices if c.strip().isdigit() and 0 < int(c.strip()) <= len(ssids)]
            if result:
                return result
            else:
                print("⚠️ Debes seleccionar al menos uno.")
        except (ValueError, IndexError):
            print("Entrada inválida.")

def save_to_env(key, value):
    set_key('.env', key, value)

def main():
    print("=== Configuración del archivo .env para UniFi + SMTP ===")

    # Credenciales UniFi
    unifi_url = input("Introduce la URL del controlador UniFi: ")
    unifi_username = input("Introduce el usuario UniFi: ")
    unifi_password = getpass("Introduce la contraseña UniFi: ")

    session = verify_unifi_credentials(unifi_url, unifi_username, unifi_password)
    if not session:
        return

    # Sitios
    sites = list_unifi_sites(session, unifi_url)
    if not sites:
        return
    selected_site = select_unifi_site(sites)
    print(f"✅ Sitio seleccionado: {selected_site['desc']} (ID: {selected_site['name']})")

    save_to_env('UNIFI_URL', unifi_url)
    save_to_env('UNIFI_USERNAME', unifi_username)
    save_to_env('UNIFI_PASSWORD', unifi_password)
    save_to_env('UNIFI_SITE', selected_site['name'])

    # SSIDs
    ssids = list_ssids(session, unifi_url, selected_site['name'])
    if ssids:
        ssids_to_omit = configure_ssids_to_omit(ssids)
        save_to_env('SSIDS_TO_OMIT', ','.join(ssids_to_omit))

    # SMTP / correo
    print("\n=== Configuración SMTP ===")
    smtp_server = input("Servidor SMTP: ")
    smtp_port = input("Puerto SMTP (por defecto 587): ") or "587"
    smtp_user = input("Usuario SMTP: ")
    smtp_password = getpass("Contraseña SMTP: ")
    email_from = input("Dirección FROM: ")
    email_to = input("Dirección TO (destino): ")

    save_to_env('SMTP_SERVER', smtp_server)
    save_to_env('SMTP_PORT', smtp_port)
    save_to_env('SMTP_USER', smtp_user)
    save_to_env('SMTP_PASSWORD', smtp_password)
    save_to_env('EMAIL_FROM', email_from)
    save_to_env('EMAIL_TO', email_to)

    # Horarios
    print("\n=== Horarios de envío y limpieza ===")
    send_times = input("Introduce horarios de envío separados por coma (ej: 08:00,12:00): ")
    clear_times = input("Introduce horarios de limpieza separados por coma (ej: 23:59): ")

    save_to_env('SEND_TIMES', send_times)
    save_to_env('CLEAR_TIMES', clear_times)

    print("\n✅ Archivo .env generado/actualizado correctamente.")

if __name__ == "__main__":
    main()
