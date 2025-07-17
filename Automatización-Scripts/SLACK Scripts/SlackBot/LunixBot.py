import os
import json
import requests
import threading
import base64
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from datetime import datetime
from pytz import timezone
import urllib3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TZ = os.getenv("TZ", "America/Argentina/Buenos_Aires")

SSL_VERIFY = os.getenv("SSL_VERIFY", "true").lower() == "true"

if not SSL_VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    logger.warning("La verificación de SSL está desactivada.")

BOT_USER_OAUTH_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OS_TICKET_API_KEY = os.getenv("OS_TICKET_API_KEY")
OS_TICKET_API_URL = os.getenv("OS_TICKET_API_URL")
API_IP = os.getenv("API_IP")

SLACK_CHANNELS_RAW = os.getenv("SLACK_CHANNELS", "")
SLACK_CHANNELS = {
    channel.split('=')[0]: channel.split('=')[1]
    for channel in SLACK_CHANNELS_RAW.split(',')
    if '=' in channel
}

# Mapeo de topicId según grupo
TOPIC_IDS = {
    "Depto1": 11,
    "Depto2": 22,
    "Depto3": 33
}

app = Flask(__name__)

def send_error_to_slack(error_message, channel_id, user_id):
    try:
        logger.info(f"Enviando mensaje de error al usuario {user_id} en canal {channel_id}")
        response = slack_api_call("chat.postEphemeral", method="POST", json_data={
            "channel": channel_id,
            "user": user_id,
            "text": f"⚠️ *Error detectado:* {error_message}"
        })
        if response and response.get("ok"):
            logger.info("Mensaje de error enviado correctamente al usuario.")
        else:
            logger.error(f"Error al enviar el mensaje de error. Respuesta de Slack: {response}")
    except Exception as e:
        logger.error(f"Error al enviar el mensaje efímero a Slack: {e}")

def slack_api_call(endpoint, method="GET", params=None, json_data=None):
    url = f"https://slack.com/api/{endpoint}"
    headers = {"Authorization": f"Bearer {BOT_USER_OAUTH_TOKEN}"}
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=params, verify=SSL_VERIFY)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=json_data, verify=SSL_VERIFY)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error en Slack API ({endpoint}): {e}")
        return None

def get_user_name(user_id):
    try:
        user_info = slack_api_call("users.info", params={'user': user_id})
        return user_info.get('user', {}).get('real_name', "Desconocido")
    except Exception as e:
        logger.error(f"Error al obtener nombre de usuario para ID {user_id}: {e}")
        return "Desconocido"

def get_images_from_slack(channel_id, max_age_minutes=60):
    messages_response = slack_api_call("conversations.history", params={'channel': channel_id, 'limit': 50})
    if not messages_response or 'messages' not in messages_response:
        logger.error("No se pudo obtener el historial de mensajes.")
        return []

    messages = messages_response['messages']
    if not messages:
        return []

    now = datetime.now(timezone(TZ)).timestamp()

    image_urls = []
    processed_requests = set()  # Para evitar procesar solicitudes duplicadas

    for message in messages:
        message_ts = float(message.get('ts', 0))
        message_age_minutes = (now - message_ts) / 60

        if message_age_minutes > max_age_minutes:
            continue

        text = message.get('text', '').strip().lower()
        if not is_valid_request(text):
            continue

        request_id = generate_request_id(message)
        if request_id in processed_requests:
            continue

        processed_requests.add(request_id)

        if 'files' in message:
            for file in message['files']:
                if file.get('mimetype', '').startswith('image/'):
                    image_urls.append(file['url_private'])

    return image_urls


def is_valid_request(text):
    keywords = ["solicitud", "ticket", "reporte", "asistencia"]
    return any(keyword in text for keyword in keywords)


def generate_request_id(message):
    user = message.get('user', 'unknown')
    text = message.get('text', '').strip()
    ts = message.get('ts', '0')
    return f"{user}:{text}:{ts}"

def download_and_encode_images(image_urls):
    headers = {"Authorization": f"Bearer {BOT_USER_OAUTH_TOKEN}"}
    attachments = []

    for url in image_urls:
        try:
            response = requests.get(url, headers=headers, verify=SSL_VERIFY)
            response.raise_for_status()
            file_name = url.split("/")[-1]
            mime_type = response.headers.get('Content-Type', 'image/png')  # Default MIME type

            encoded_image = base64.b64encode(response.content).decode('utf-8')
            attachments.append({file_name: f"data:{mime_type};base64,{encoded_image}"})
            logger.info(f"Imagen descargada y procesada: {file_name}")
        except requests.RequestException as e:
            logger.error(f"Error al descargar la imagen {url}: {e}")
    return attachments


def process_ticket_creation(channel_id, group, subject):
    message_text, author_user_id, image_urls = get_consecutive_messages_and_images(channel_id)

    if not message_text or not author_user_id:
        logger.error("No se pudo obtener los mensajes o el autor.")
        return

    author_user_name = get_user_name(author_user_id)

    group_from_origin = SLACK_CHANNELS.get(channel_id, "desconocido").lower()

    topic_id = TOPIC_IDS.get(group, 22)

    attachments = download_and_encode_images(image_urls)

    ticket_id = create_ticket(author_user_name, message_text, group_from_origin, subject, topic_id, attachments)

    slack_api_call("chat.postMessage", method="POST", json_data={
        "channel": channel_id,
        "text": f"✅ Ticket generado con ID: {ticket_id}.\nAsunto: *{subject}*\nSolicitado por: *{author_user_name}*"
    })

    destination_channel_id = next((cid for cid, name in SLACK_CHANNELS.items() if name == group), None)
    if destination_channel_id:
        slack_api_call("chat.postMessage", method="POST", json_data={
            "channel": destination_channel_id,
            "text": f"🚨 *Nuevo ticket generado desde el grupo {group_from_origin.upper()}* 🚨\n"
                    f"ID del Ticket: *{ticket_id}*\nAsunto: *{subject}*\nSolicitado por: *{author_user_name}*"
        })
        logger.info(f"Mensaje replicado al canal de destino: {group} ({destination_channel_id})")
    else:
        logger.warning(f"No se pudo encontrar el canal de destino para el grupo: {group}.")

def create_ticket(user_name, slack_message, group_from_origin, subject, topic_id,attachments):
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": OS_TICKET_API_KEY
    }

    body = {
        "alert": True,
        "autorespond": True,
        "source": "API",
        "name": user_name,
        "topicId": topic_id,
        "email": f"{group_from_origin}@ejemplo.ejemplo.com.ar",  
        "subject": subject,
        "ip": API_IP,
        "message": f"Se comunicó {user_name} solicitando lo siguiente:\n{slack_message}\n\n",
	"attachments": attachments
    }

    logger.info(f"Cuerpo del ticket enviado a osTicket: {json.dumps(body, indent=2)}")

    try:
        response = requests.post(OS_TICKET_API_URL, headers=headers, json=body, verify=SSL_VERIFY)
        response.raise_for_status()
        json_response = response.json()
        return str(json_response) if isinstance(json_response, int) else json_response.get('ticket', {}).get('id', "desconocido")
    except requests.RequestException as e:
        logger.error(f"Error al crear el ticket: {e}")
        return "desconocido"


def get_consecutive_messages_and_images(channel_id, max_age_minutes=60):
    messages_response = slack_api_call("conversations.history", params={'channel': channel_id, 'limit': 50})
    if not messages_response or 'messages' not in messages_response:
        logger.error("No se pudo obtener el historial de mensajes.")
        return None, None, []

    messages = messages_response['messages']
    if not messages:
        return None, None, []

    now = datetime.now(timezone(TZ)).timestamp()

    last_user_id = messages[0].get('user')
    collected_messages = []
    image_urls = []

    for msg in messages:
        if msg.get('user') == last_user_id:
            message_ts = float(msg.get('ts', 0))
            message_age_minutes = (now - message_ts) / 60

            if message_age_minutes > max_age_minutes:
                continue  # Ignorar mensajes antiguos

            collected_messages.append(msg.get('text', '').strip())

            if 'files' in msg:
                for file in msg['files']:
                    if file.get('mimetype', '').startswith('image/'):
                        image_urls.append(file['url_private'])
        else:
            break  

    collected_messages.reverse()  # Ordenar cronológicamente
    return "\n".join(collected_messages), last_user_id, image_urls

last_response_time = {}

def check_message_time():
    try:
        tz = timezone(TZ)
        now = datetime.now(tz)
        logger.info(f"Hora actual: {now.hour}:{now.minute} en zona horaria: {TZ}")
        fuera_de_horario = 8 <= now.hour < 24 or 0 <= now.hour < 8 #Establecer horario correspondiente
        logger.info(f"¿Fuera de horario?: {fuera_de_horario}")
        return fuera_de_horario
    except Exception as e:
        logger.error(f"Error al verificar el horario: {e}")
        return False

def send_message(text, channel_id, image_url=None):
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {BOT_USER_OAUTH_TOKEN}"}

    if image_url:
        payload = {
            "channel": channel_id,
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text},
                },
                {
                    "type": "image",
                    "image_url": image_url,
                    "alt_text": "Imagen adjunta",
                },
            ],
        }
    else:
        payload = {"channel": channel_id, "text": text}

    try:
        response = requests.post(url, headers=headers, json=payload, verify=SSL_VERIFY)
        response.raise_for_status()
        logger.info(f"Mensaje enviado a {channel_id}: {text}")
    except requests.RequestException as e:
        logger.error(f"Error al enviar mensaje a {channel_id}: {e}")

RESPONSE_COOLDOWN = 600  # En segundos (10 minutos)

@app.route("/slack/events", methods=["POST"])
def slack_events():
    global last_response_time

    data = request.json
    logger.info(f"Datos recibidos del evento: {json.dumps(data, indent=2)}")

    if 'type' in data and data['type'] == 'url_verification':
        return jsonify({"challenge": data['challenge']})

    if 'event' in data:
        event = data['event']
        if 'subtype' not in event and event.get('user'):
            channel_id = event.get('channel', '')
            user_id = event.get('user', '')

            logger.info(f"Mensaje recibido en canal: {channel_id} por usuario: {user_id}")

            if channel_id in SLACK_CHANNELS:
                group_name = SLACK_CHANNELS[channel_id]
                logger.info(f"El canal {channel_id} pertenece al grupo: {group_name}")

                if check_message_time():
                    now = datetime.now()
                    last_sent = last_response_time.get(channel_id)

                    if not last_sent or (now - last_sent).total_seconds() > RESPONSE_COOLDOWN:
                        logger.info(f"Enviando mensaje fuera de horario al canal: {channel_id}")
                        send_message(
                            f"Se comunicó fuera del horario de atención del grupo *{group_name}*. "
                            "Favor de proceder con la comunicación correspondiente según el siguiente escalonamiento:",
                            channel_id,
                            image_url="https://drive.google.com/uc?id=",#Ingresar el ID correspondiente
                        )
                        last_response_time[channel_id] = now
                    else:
                        logger.info(f"Mensaje fuera de horario ya enviado recientemente al canal: {channel_id}")
                else:
                    logger.info("El mensaje no está fuera del horario de atención.")
            else:
                logger.warning(f"El canal {channel_id} no está configurado en SLACK_CHANNELS.")
    return '', 200


@app.route('/slack/commands/genticket', methods=['POST'])
def genticket():
    channel_id = request.form.get('channel_id')
    user_id = request.form.get('user_id')
    command_text = request.form.get('text').strip()

    parts = command_text.split(' ', 1)
    if len(parts) < 2:
        return jsonify({'text': "Uso incorrecto. Usa: /genticket <grupo> \"Asunto\""}), 200

    group, subject = parts[0].lower(), parts[1].strip('"')

    if group not in TOPIC_IDS:
        return jsonify({'text': f"Grupo no válido: {group}. Usa uno de los siguientes: Depto1, Depto2, Depto3."}), 200

    threading.Thread(target=process_ticket_creation, args=(channel_id, group, subject)).start()
    return jsonify({'text': "Procesando la creación del ticket... ⏳"}), 200

@app.route('/slack/commands/replicar', methods=['POST'])
def reply():
    channel_id = request.form.get('channel_id')
    user_id = request.form.get('user_id')
    command_text = request.form.get('text', '').strip()  

    if not command_text:
        return jsonify({'text': "Uso incorrecto. Debes proporcionar un mensaje. Ejemplo: `/reply Este es un mensaje`"}), 200

    image_url = "https://drive.google.com/uc?id=" #Ingresar El ID correspondiente

    for channel, group_name in SLACK_CHANNELS.items():
        try:
            logger.info(f"Replicando mensaje en canal: {channel} para grupo: {group_name}")
            send_message(
                f"*🚨Aviso Informativo: *\n{command_text}",
                channel,
                image_url=image_url
            )
        except Exception as e:
            logger.error(f"Error al enviar mensaje al canal {channel}: {e}")

    return jsonify({'text': f"Mensaje replicado en los grupos configurados:\n{', '.join(SLACK_CHANNELS.values())}"}), 200


if __name__ == '__main__':
    app.run(port=3000)
