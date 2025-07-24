import os
import re
import requests
import urllib3
import json
import time
from datetime import datetime
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Cargar variables de entorno
load_dotenv()

# Configuración UniFi
controller_url = os.getenv("UNIFI_URL")
username = os.getenv("UNIFI_USERNAME")
password = os.getenv("UNIFI_PASSWORD")
site_id = os.getenv("UNIFI_SITE")
filtro_ssid = os.getenv("SSIDS_TO_OMIT", "").split(',')

# Horarios desde .env (listas de strings "HH:MM")
SEND_TIMES = [t.strip() for t in os.getenv("SEND_TIMES", "").split(",") if t.strip()]
CLEAR_TIMES = [t.strip() for t in os.getenv("CLEAR_TIMES", "").split(",") if t.strip()]

# Configuración correo
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO").split(',')

# Desactivar warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Archivo JSON para estado dispositivos
DEVICES_STATUS_FILE = "devices_status.json"

def login(controller_url, username, password):
    login_url = f'{controller_url}/api/login'
    payload = {"username": username, "password": password}
    try:
        response = requests.post(login_url, json=payload, verify=False)
        response.raise_for_status()
        if response.status_code == 200:
            print(f"[{datetime.now()}] Login exitoso.")
            return response.cookies
    except requests.exceptions.HTTPError as e:
        print(f"Error HTTP en login: {e}")
    except Exception as e:
        print(f"Error en login: {e}")
    return None

def fetch_aps(cookies):
    aps_url = f'{controller_url}/api/s/{site_id}/stat/device-basic'
    response = requests.get(aps_url, cookies=cookies, verify=False)
    response.raise_for_status()
    return response.json()

def fetch_devices(cookies):
    devices_url = f'{controller_url}/api/s/{site_id}/stat/sta'
    response = requests.get(devices_url, cookies=cookies, verify=False)
    response.raise_for_status()
    return response.json()

def store_devices_in_table(devices_data, ap_names):
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
        }
        devices_table.append(device_entry)
    return devices_table

def filter_unknown_devices(devices_table):
    filtered_devices = []
    for device in devices_table:
        essid = device.get('essid', '')
        if any(word.lower() in essid.lower() for word in filtro_ssid):
            continue
        if not device.get('name'):
            filtered_devices.append(device)
    return filtered_devices

def load_devices_status():
    if os.path.exists(DEVICES_STATUS_FILE):
        with open(DEVICES_STATUS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_devices_status(devices_status):
    with open(DEVICES_STATUS_FILE, 'w') as f:
        json.dump(devices_status, f, indent=4)

def add_or_update_device(device):
    devices_status = load_devices_status()
    for entry in devices_status:
        if entry['mac'] == device['mac']:
            entry.update({
                'ip': device['ip'],
                'hostname': device['hostname'],
                'essid': device['essid'],
                'ap_name': device['ap_name'],
                'timestamp': device['timestamp'],
                'sent_status': entry.get('sent_status', "no enviado")
            })
            break
    else:
        devices_status.append({
            'mac': device['mac'],
            'ip': device['ip'],
            'hostname': device['hostname'],
            'essid': device['essid'],
            'ap_name': device['ap_name'],
            'timestamp': device['timestamp'],
            'sent_status': "no enviado",
        })
    save_devices_status(devices_status)

def get_unsent_devices():
    devices_status = load_devices_status()
    return [d for d in devices_status if d.get('sent_status') == "no enviado"]

def mark_devices_as_sent(devices):
    devices_status = load_devices_status()
    macs_to_mark = {d['mac'] for d in devices}
    for entry in devices_status:
        if entry['mac'] in macs_to_mark:
            entry['sent_status'] = "enviado"
    save_devices_status(devices_status)

def clear_device_status():
    save_devices_status([])
    print(f"[{datetime.now()}] Archivo de estado vaciado.")

def send_email(devices):
    if not devices:
        return
    subject = f"Dispositivos desconocidos detectados - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    body_lines = []
    for d in devices:
        line = (f"MAC: {d['mac']}, IP: {d['ip']}, Hostname: {d['hostname']}, "
                f"SSID: {d['essid']}, AP: {d['ap_name']}, Detectado en: {d['timestamp']}")
        body_lines.append(line)
    body = "\n".join(body_lines)

    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = ", ".join(EMAIL_TO)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"[{datetime.now()}] Email enviado con {len(devices)} dispositivos desconocidos.")
    except Exception as e:
        print(f"Error enviando email: {e}")

def main_loop():
    cookies = login(controller_url, username, password)
    if not cookies:
        print("No se pudo iniciar sesión en UniFi. Terminando.")
        return

    while True:
        try:
            aps_data = fetch_aps(cookies)
            ap_names = {ap['mac'].lower(): ap['name'] for ap in aps_data.get('data', [])} if aps_data else {}

            devices_data = fetch_devices(cookies)
            devices_table = store_devices_in_table(devices_data, ap_names)
            unknown_devices = filter_unknown_devices(devices_table)

            if unknown_devices:
                for device in unknown_devices:
                    add_or_update_device(device)

            current_time = datetime.now().strftime('%H:%M')

            if current_time in SEND_TIMES:
                devices_to_send = get_unsent_devices()
                if devices_to_send:
                    send_email(devices_to_send)
                    mark_devices_as_sent(devices_to_send)
                else:
                    print(f"[{datetime.now()}] No hay dispositivos nuevos para enviar.")

            if current_time in CLEAR_TIMES:
                clear_device_status()

            time.sleep(30)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print(f"[{datetime.now()}] Sesión expirada, reintentando login...")
                cookies = login(controller_url, username, password)
                if not cookies:
                    print(f"[{datetime.now()}] No se pudo renovar sesión, esperando 60 segundos antes de reintentar.")
                    time.sleep(60)
            else:
                print(f"Error HTTP: {e}")
                time.sleep(60)
        except Exception as e:
            print(f"Error inesperado: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main_loop()
