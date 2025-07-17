import os
import re
import requests
import urllib3
import base64
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from dotenv import load_dotenv
from datetime import datetime
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Configuración de filtros
controller_url = os.getenv("UNIFI_URL")
username = os.getenv("UNIFI_USERNAME")
password = os.getenv("UNIFI_PASSWORD")
site_id = os.getenv("UNIFI_SITE")
filtro_ssid = os.getenv("SSIDS_TO_OMIT", "").split(',')

# Verificación de variables de entorno 
missing_vars = []
if not controller_url:
    missing_vars.append("UNIFI_URL")
if not username:
    missing_vars.append("UNIFI_USERNAME")
if not password:
    missing_vars.append("UNIFI_PASSWORD")
if not site_id:
    missing_vars.append("UNIFI_SITE")

if missing_vars:
    raise ValueError(f"Una o más variables de entorno no están definidas: {', '.join(missing_vars)}")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Obtiene el directorio del script
script_dir = os.path.dirname(os.path.abspath(__file__))
output_file = os.path.join(script_dir, 'log.txt')

def login(controller_url, username, password):
    """Realiza el login y obtiene una cookie de sesión."""
    login_url = f'{controller_url}/api/login'
    payload = {
        'username': username,
        'password': password
    }
    try:
        response = requests.post(login_url, json=payload, verify=False)
        response.raise_for_status()
        if response.status_code == 200:
            print("Login exitoso.")
            return response.cookies
    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP en el login: {http_err}")
    except Exception as err:
        print(f"Error al realizar el login: {err}")
    return None

def fetch_aps(cookies):
    """Obtener todos los puntos de acceso conectados."""
    aps_url = f'{controller_url}/api/s/{site_id}/stat/device-basic'
    try:
        response = requests.get(aps_url, cookies=cookies, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP al obtener puntos de acceso: {http_err}")
    except Exception as err:
        print(f"Error al obtener puntos de acceso: {err}")
    return None

def fetch_devices(cookies):
    """Obtener todos los dispositivos conectados."""
    devices_url = f'{controller_url}/api/s/{site_id}/stat/sta'
    try:
        response = requests.get(devices_url, cookies=cookies, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP al obtener dispositivos: {http_err}")
    except Exception as err:
        print(f"Error al obtener dispositivos: {err}")
    return None

def store_devices_in_table(devices_data, ap_names):
    """Almacenar los datos de los dispositivos en una tabla."""
    devices_table = []
    for device in devices_data.get('data', []):
        device_entry = {
            'mac': device.get('mac', 'Desconocido'),
            'ip': device.get('ip', 'Desconocido'),
            'hostname': device.get('hostname', 'Desconocido'),
            'essid': device.get('essid', 'Desconocido'),
            'name': device.get('name', ''),
            'ap_mac': device.get('ap_mac', 'Desconocido'),
            'ap_name': ap_names.get(device.get('ap_mac', '').lower(), 'Desconocido'),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'user_id': device.get('_id', 'Desconocido')
        }
        devices_table.append(device_entry)
    return devices_table

def filter_unknown_devices(devices_table):
    """Filtrar dispositivos desconocidos."""
    filtered_devices = []
    for device in devices_table:
        essid = device.get('essid', '')

        # Omitir dispositivos de ESSID que contengan palabras clave en 'filtro_ssid'
        if any(word.lower() in essid.lower() for word in filtro_ssid):
            continue

        # Agregar dispositivos que no tienen nombre
        if not device.get('name'):
            filtered_devices.append(device)
    
    return filtered_devices

def buscar_macs_en_pfsense(mac_list):
    """Buscar direcciones MAC en pfSense y obtener el nombre del cliente asociado."""
    load_dotenv()

    URL = os.getenv('PFSENSE_URL')
    USER = os.getenv('PFSENSE_USERNAME')
    PASS = os.getenv('PFSENSE_PASSWORD')

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument('--headless')  
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("--allow-insecure-localhost")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(URL)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'usernamefld')))

        username_field = driver.find_element(By.ID, 'usernamefld')
        password_field = driver.find_element(By.ID, 'passwordfld')
        username_field.send_keys(USER)
        password_field.send_keys(PASS)
        password_field.send_keys(Keys.RETURN)

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//table/tbody/tr")))

        # Acceder a la página de leases DHCP
        driver.get(URL + 'status_dhcp_leases.php')
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//table/tbody/tr")))

        # Obtener todas las filas de la tabla de leases DHCP
        rows = driver.find_elements(By.XPATH, "//table/tbody/tr")

        # Crear un diccionario con MACs y nombres de cliente
        mac_to_client_id = {}
        for row in rows:
            try:
                # Aquí buscamos la celda que contiene la MAC (columna 3)
                mac_cell = row.find_element(By.XPATH, "./td[3]").text.lower().strip()

                # Buscar la celda con el nombre del cliente (columna 4)
                client_id_cell = row.find_element(By.XPATH, "./td[4]").text.strip()

                # Agregar la MAC y el nombre del cliente al diccionario
                mac_to_client_id[mac_cell] = client_id_cell
            except Exception as e:
                print(f"Error procesando fila: {e}")
                continue

        # Buscar cada MAC de la lista en el diccionario
        results = {}
        for mac in mac_list:
            results[mac] = mac_to_client_id.get(mac.lower(), "No se encontró Client ID")

        return results

    except Exception as e:
        print(f"Ocurrió un error: {e}")
        return {}

    finally:
        driver.quit()

def get_registered_macs(output_file):
    """Obtiene las MACs ya registradas del archivo log.txt"""
    registered_macs = set()
    mac_pattern = re.compile(r"MAC: ([0-9a-fA-F:]{17})")  # Patrón para MAC addresses

    if os.path.exists(output_file):
        with open(output_file, 'r') as log_file:
            for line in log_file:
                if "No se encontró Client ID" in line:
                    continue  # Omitir líneas que no contienen MACs
                
                match = mac_pattern.search(line)  # Buscar el patrón de MAC en la línea
                if match:
                    mac = match.group(1).strip()  # Extraer la MAC del match
                    registered_macs.add(mac)
                else:
                    print(f"Línea malformada o sin MAC: {line.strip()}")  # Muestra la línea sin formatear
    
    return registered_macs

# Horarios de envío y limpieza
SEND_TIMES = ['08:00', '10:00', '14:00']  # Horarios de envío
CLEAR_TIMES = ['08:30', '14:00']  # Horarios de limpieza

# Desactivar advertencias de verificación de certificados
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Verificar si las variables de entorno están definidas
missing_vars = []
if not controller_url:
    missing_vars.append("UNIFI_URL")
if not username:
    missing_vars.append("UNIFI_USERNAME")
if not password:
    missing_vars.append("UNIFI_PASSWORD")
if not site_id:
    missing_vars.append("UNIFI_SITE")

if missing_vars:
    raise ValueError(f"Una o más variables de entorno no están definidas: {', '.join(missing_vars)}")


def load_devices_status():
    """Carga el archivo centralizado de dispositivos con su estado."""
    if os.path.exists('devices_status.json'):
        with open('devices_status.json', 'r') as file:
            return json.load(file)
    return []


def save_devices_status(devices_status):
    """Guarda el estado de los dispositivos en el archivo."""
    with open('devices_status.json', 'w') as file:
        json.dump(devices_status, file, indent=4)


def add_or_update_device(device, client_name):
    """Añade o actualiza un dispositivo en el archivo centralizado."""
    devices_status = load_devices_status()
    
    # Verificar si el dispositivo ya existe
    for entry in devices_status:
        if entry['mac'] == device['mac']:
            # Actualizar el dispositivo existente
            entry.update({
                'ip': device['ip'],
                'hostname': device['hostname'],
                'essid': device['essid'],
                'ap_name': device['ap_name'],
                'client_name': client_name,
                'timestamp': device['timestamp'],
                'sent_status': entry['sent_status'],  # Mantener el estado actual
            })
            break
    else:
        # Añadir un nuevo dispositivo
        devices_status.append({
            'mac': device['mac'],
            'ip': device['ip'],
            'hostname': device['hostname'],
            'essid': device['essid'],
            'ap_name': device['ap_name'],
            'client_name': client_name,
            'timestamp': device['timestamp'],
            'sent_status': "no enviado",
        })
    
    save_devices_status(devices_status)


def get_unsent_devices():
    """Obtiene los dispositivos que no han sido enviados."""
    devices_status = load_devices_status()
    return [device for device in devices_status if device['sent_status'] == "no enviado"]


def mark_devices_as_sent(devices):
    """Marca los dispositivos como enviados en el archivo centralizado."""
    devices_status = load_devices_status()
    for device in devices:
        for entry in devices_status:
            if entry['mac'] == device['mac']:
                entry['sent_status'] = "enviado"
                break
    save_devices_status(devices_status)


def clear_device_status():
    """Vacía el archivo de estado de dispositivos."""
    with open('devices_status.json', 'w') as file:
        json.dump([], file, indent=4)
    print("Archivo de estado de dispositivos vaciado.")


def login(controller_url, username, password):
    """Realiza el login y obtiene una cookie de sesión."""
    login_url = f'{controller_url}/api/login'
    payload = {
        'username': username,
        'password': password
    }
    try:
        response = requests.post(login_url, json=payload, verify=False)
        response.raise_for_status()
        if response.status_code == 200:
            print("Login exitoso.")
            return response.cookies
    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP en el login: {http_err}")
    except Exception as err:
        print(f"Error al realizar el login: {err}")
    return None


def fetch_aps(cookies):
    """Obtener todos los puntos de acceso conectados."""
    aps_url = f'{controller_url}/api/s/{site_id}/stat/device-basic'
    try:
        response = requests.get(aps_url, cookies=cookies, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP al obtener puntos de acceso: {http_err}")
    except Exception as err:
        print(f"Error al obtener puntos de acceso: {err}")
    return None


def fetch_devices(cookies):
    """Obtener todos los dispositivos conectados."""
    devices_url = f'{controller_url}/api/s/{site_id}/stat/sta'
    try:
        response = requests.get(devices_url, cookies=cookies, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP al obtener dispositivos: {http_err}")
    except Exception as err:
        print(f"Error al obtener dispositivos: {err}")
    return None


def store_devices_in_table(devices_data, ap_names):
    """Almacenar los datos de los dispositivos en una tabla."""
    devices_table = []
    for device in devices_data.get('data', []):
        device_entry = {
            'mac': device.get('mac', 'Desconocido'),
            'ip': device.get('ip', 'Desconocido'),
            'hostname': device.get('hostname', 'Desconocido'),
            'essid': device.get('essid', 'Desconocido'),
            'name': device.get('name', ''),
            'ap_mac': device.get('ap_mac', 'Desconocido'),
            'ap_name': ap_names.get(device.get('ap_mac', '').lower(), 'Desconocido'),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'user_id': device.get('_id', 'Desconocido')
        }
        devices_table.append(device_entry)
    return devices_table


def filter_unknown_devices(devices_table):
    """Filtrar dispositivos desconocidos."""
    filtered_devices = []
    for device in devices_table:
        essid = device.get('essid', '')
        if any(word.lower() in essid.lower() for word in filtro_ssid):
            continue
        if not device.get('name'):
            filtered_devices.append(device)
    return filtered_devices


def send_log_to_osticket(devices):
    """Enviar dispositivos desconocidos a osTicket con formato diferenciado según el estado de pfSense."""
    api_key = os.getenv("API_KEY")
    api_email = os.getenv("API_EMAIL")
    api_ip = os.getenv("API_IP")
    topic_id = os.getenv("TOPIC_ID")
    subject = os.getenv("SUBJECT")
    title = os.getenv("TITLE")

    headers = {"Content-Type": "application/json", "X-API-Key": api_key}

    # Crear el cuerpo del mensaje con formato diferenciado
    message_lines = []
    for device in devices:
        device_info = (
            f"MAC: {device['mac']}, "
            f"IP: {device['ip']}, "
            f"Hostname: {device['hostname']}, "
            f"SSID: {device['essid']}, "
            f"AP: {device['ap_name']}, "
            f"Hora de detección: {device['timestamp']}"
        )
        if not device['client_name'] or device['client_name'] == "No se encontró Client ID":
            # Caso: no hay nombre en pfSense
            message_lines.append(f"Se solicita el bloqueo del dispositivo:\n{device_info}")
        else:
            # Caso: se encontró un nombre en pfSense
            message_lines.append(
                f"Se solicita la asignación de nombre del dispositivo:\n{device_info}\n"
                f"Nombre sugerido desde pfSense: {device['client_name']}"
            )

    message_content = f"{title}\n\n" + "\n\n".join(message_lines)

    body = {
        "alert": True,
        "autorespond": True,
        "source": "API",
        "name": "Reportes",
        "topicId": int(topic_id),
        "email": api_email,
        "subject": subject,
        "ip": api_ip,
        "message": message_content,
    }

    try:
        response = requests.post("https://ejemplo-test.ejemplo.com.ar/api/tickets.json", headers=headers, json=body, verify=False)
        response.raise_for_status()
        print("Registro enviado a osTicket exitosamente.")
    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP al enviar el registro a osTicket: {http_err}")
    except Exception as err:
        print(f"Error al enviar el registro a osTicket: {err}")



def main():
    cookies = login(controller_url, username, password)
    if not cookies:
        return

    # Obtener los puntos de acceso
    aps_data = fetch_aps(cookies)
    ap_names = {ap['mac'].lower(): ap['name'] for ap in aps_data.get('data', [])} if aps_data else {}

    # Obtener los dispositivos conectados
    devices_data = fetch_devices(cookies)
    devices_table = store_devices_in_table(devices_data, ap_names)

    # Filtrar dispositivos desconocidos
    unknown_devices = filter_unknown_devices(devices_table)

    if unknown_devices:
        # Obtener las MACs de los dispositivos desconocidos
        mac_list = [device['mac'] for device in unknown_devices]

        # Buscar nombres en pfSense
        client_names = buscar_macs_en_pfsense(mac_list)

        # Actualizar o añadir los dispositivos con los nombres obtenidos de pfSense
        for device in unknown_devices:
            mac = device['mac']
            client_name = client_names.get(mac, "No se encontró Client ID")
            add_or_update_device(device, client_name)

    # Verificar si es hora de enviar dispositivos
    if datetime.now().strftime('%H:%M') in SEND_TIMES:
        devices_to_send = get_unsent_devices()
        if devices_to_send:
            # Enviar dispositivos a la API de osTicket en texto
            send_log_to_osticket(devices_to_send)

            # Cambiar el estado de los dispositivos a "enviado"
            mark_devices_as_sent(devices_to_send)
        else:
            print("No hay dispositivos nuevos para enviar.")

    # Verificar si es hora de limpiar los logs
    if datetime.now().strftime('%H:%M') in CLEAR_TIMES:
        clear_device_status()


if __name__ == "__main__":
    while True:
        main()
        time.sleep(30)
