import requests
import sys
import time
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('SLACK_TOKEN')
channel_id = os.getenv('CHANNEL_ID')

history_api_url = f'https://slack.com/api/conversations.history?channel={channel_id}&limit=1000&cursor='
delete_api_url = 'https://slack.com/api/chat.delete'
replies_api_url = f'https://slack.com/api/conversations.replies?channel={channel_id}&ts='
delay = 0.3 


def request(url, data=None):
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json'
    }
    if data:
        response = requests.post(url, json=data, headers=headers)
    else:
        response = requests.get(url, headers=headers)
    
    return response.json()

async def sleep(seconds):
    await asyncio.sleep(seconds)

async def delete_messages(thread_ts, messages):
    if not messages:
        return

    message = messages.pop(0)

    if message.get('thread_ts') != thread_ts:
        await fetch_and_delete_messages(message['thread_ts'], '')
    else:
        response = request(delete_api_url, {'channel': channel_id, 'ts': message['ts']})

        if response.get('ok'):
            print(f"{message['ts']} {'reply' if thread_ts else ''} deleted!")
        else:
            print(f"{message['ts']} could not be deleted! ({response['error']})")

            if response['error'] == 'ratelimited':
                await sleep(1)
                global delay
                delay += 0.1  # Aumentar el retraso si hay un límite de velocidad
                messages.insert(0, message)  # Reinsertar el mensaje para volver a intentar

    await sleep(delay)
    await delete_messages(thread_ts, messages)

async def fetch_and_delete_messages(thread_ts, cursor):
    response = request((f"{replies_api_url}{thread_ts}&cursor=" if thread_ts else history_api_url) + cursor)

    if not response.get('ok'):
        print(response['error'])
        return

    if not response.get('messages'):
        return

    await delete_messages(thread_ts, response['messages'])

    if response.get('has_more'):
        await fetch_and_delete_messages(thread_ts, response['response_metadata']['next_cursor'])

async def main():
    await fetch_and_delete_messages(None, '')

if __name__ == '__main__':
    asyncio.run(main())
