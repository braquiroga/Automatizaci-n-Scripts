import os
import requests
import json
from getpass import getpass
from dotenv import load_dotenv, set_key
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv(dotenv_path='.env')

def verify_unifi_credentials(url, username, password):
    try:
        session = requests.Session()
        login_data = {
            "username": username,
            "password": password
        }
        headers = {"Content-Type": "application/json"}
        response = session.post(f"{url}/api/login", data=json.dumps(login_data), headers=headers, verify=False)

        if response.status_code == 200:
            print("Credenciales UniFi verificadas correctamente.")
            return session
        else:
            print("Error al verificar credenciales UniFi.")
            return None
    except Exception as e:
        print(f"Error al conectar con UniFi: {e}")
        return None

def verify_pfsense_credentials(url, username, password):
    try:
        response = requests.get(url, auth=(username, password), verify=False)

        if response.status_code == 200:
            print("Credenciales pfSense verificadas correctamente.")
            return True
        else:
            print("Error al verificar credenciales pfSense.")
            return False
    except Exception as e:
        print(f"Error al conectar con pfSense: {e}")
        return False

def list_unifi_sites(session, url):
    try:
        response = session.get(f"{url}/api/self/sites", verify=False)
        sites = response.json()["data"]
        print("Sitios disponibles en UniFi:")
        for i, site in enumerate(sites):
            print(f"{i + 1}. {site['desc']} (ID: {site['name']})")
        return sites
    except Exception as e:
        print(f"Error al listar sitios de UniFi: {e}")
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
            print("Por favor, ingresa un número válido.")

def list_ssids(session, url, site_id):
    try:
        response = session.get(f"{url}/api/s/{site_id}/stat/device", verify=False)
        aps = response.json()['data']
        
        ssids = set()  # Usamos un set para evitar SSIDs duplicados
        for ap in aps:
            if 'vap_table' in ap:
                for vap in ap['vap_table']:
                    ssids.add(vap['essid'])
        
        return list(ssids)  # Convertimos el set en lista
    except Exception as e:
        print(f"Error al listar SSIDs: {e}")
        return []

def configure_ssids_to_omit(ssids):
    ssids_to_omit = []
    while True:
        try:
            print("Selecciona los SSIDs que deseas omitir (separados por comas):")
            
            for i, ssid in enumerate(ssids):
                print(f"{i + 1}. {ssid}")

            choices = input("Introduce los números de los SSIDs a omitir (ej: 1,3): ").split(',')
            ssids_to_omit = [ssids[int(choice.strip()) - 1] for choice in choices if 0 < int(choice.strip()) <= len(ssids)]

            if ssids_to_omit:
                break
            else:
                print("Por favor, selecciona al menos un SSID.")
        except (ValueError, IndexError):
            print("Entrada inválida. Asegúrate de introducir números válidos separados por comas.")
    
    return ssids_to_omit

def save_to_env(key, value):
    set_key('.env', key, value)

def main():
    # Solicitar las credenciales de UniFi y pfSense
    unifi_url = input("Introduce la URL del controlador UniFi: ")
    unifi_username = input("Introduce el nombre de usuario de UniFi: ")
    unifi_password = getpass("Introduce la contraseña de UniFi: ")

    pfsense_url = input("Introduce la URL de pfSense: ")
    pfsense_username = input("Introduce el nombre de usuario de pfSense: ")
    pfsense_password = getpass("Introduce la contraseña de pfSense: ")

    # Verificar credenciales UniFi
    unifi_session = verify_unifi_credentials(unifi_url, unifi_username, unifi_password)
    if not unifi_session:
        return

    # Verificar credenciales pfSense
    if not verify_pfsense_credentials(pfsense_url, pfsense_username, pfsense_password):
        return

    # Listar sitios disponibles en UniFi
    sites = list_unifi_sites(unifi_session, unifi_url)
    if not sites:
        return

    # Seleccionar un sitio
    selected_site = select_unifi_site(sites)
    print(f"Sitio seleccionado: {selected_site['desc']} (ID: {selected_site['name']})")

    # Guardar las credenciales y el sitio seleccionado en el archivo variables.env
    save_to_env('UNIFI_URL', unifi_url)
    save_to_env('UNIFI_USERNAME', unifi_username)
    save_to_env('UNIFI_PASSWORD', unifi_password)
    save_to_env('PFSENSE_URL', pfsense_url)
    save_to_env('PFSENSE_USERNAME', pfsense_username)
    save_to_env('PFSENSE_PASSWORD', pfsense_password)
    save_to_env('UNIFI_SITE', selected_site['name'])

    # Mostrar los SSIDs disponibles del sitio seleccionado
    ssids = list_ssids(unifi_session, unifi_url, selected_site['name'])
    if not ssids:
        return

    # Configurar los SSIDs a omitir
    ssids_to_omit = configure_ssids_to_omit(ssids)
    save_to_env('SSIDS_TO_OMIT', ','.join(ssids_to_omit))

    # Solicitar las variables adicionales y guardarlas
    api_key = input("Introduce el API_KEY: ")
    api_email = input("Introduce el API_EMAIL: ")
    api_ip = input("Introduce el API_IP: ")
    topic_id = input("Introduce el TOPIC_ID: ")
    subject = input("Introduce el SUBJECT: ")
    title = input("Introduce el TITLE: ")

    save_to_env('API_KEY', api_key)
    save_to_env('API_EMAIL', api_email)
    save_to_env('API_IP', api_ip)
    save_to_env('TOPIC_ID', topic_id)
    save_to_env('SUBJECT', subject)
    save_to_env('TITLE', title)

    print("Credenciales y configuraciones guardadas en el archivo variables.env")

if __name__ == "__main__":
    main()
