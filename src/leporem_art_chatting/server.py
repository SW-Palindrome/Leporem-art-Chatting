import asyncio
import logging

import requests
import socketio

from leporem_art_chatting.settings import LOGIN_URL, MESSAGE_UPLOAD_URL

logger = logging.getLogger(__name__)
sio = socketio.AsyncServer(async_mode='asgi')
app = socketio.ASGIApp(sio)


@sio.event
async def connect(sid, environ):
    logger.info(f'connect {sid}')


@sio.event
async def authenticate(sid, data):
    response = requests.post(LOGIN_URL, data={'id_token': data['id_token']})
    if not response.status_code == 200:
        await sio.disconnect(sid)
        return

    user_id = response.json()['user_id']
    logging.info(f'authenticate {user_id}')

    async with sio.session(sid) as session:
        session['is_authenticated'] = True
        session['id_token'] = data['id_token']
        session['user_id'] = user_id
        sio.enter_room(sid, user_id)


async def _validate_session_login(sid):
    async with sio.session(sid) as session:
        if not session['is_authenticated']:
            await sio.disconnect(sid)


@sio.event
async def send_message(sid, data):
    await _validate_session_login(sid)
    await _migrate_message(sid, data)


async def _migrate_message(sid, data):
    async with sio.session(sid) as session:
        headers = {
            'Authorization': f'Palindrome {session["id_token"]}',
        }
        send_data = {
            'chat_room_uuid': data['chat_room_uuid'],
            'text': data['message'],
            'message_uuid': data['message_uuid'],
        }

        response = requests.post(MESSAGE_UPLOAD_URL, data=send_data, headers=headers)
        if response.status_code != 201:
            raise Exception(f'message upload failed with {response.text}')

        await asyncio.gather(
            sio.emit('message_registered', {
                'message_uuid': data['message_uuid'],
                'chat_room_uuid': data['chat_room_uuid'],
            }, room=session['user_id']),
            sio.emit('receive_message', {
                'chat_room_uuid': data['chat_room_uuid'],
                'message': data['message'],
                'message_uuid': data['message_uuid'],
            }, room=data['opponent_user_id']),
        )


@sio.event
async def disconnect(sid):
    logger.info(f'disconnect {sid}')


def run_server():
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=80, log_level='info')


if __name__ == '__main__':
    run_server()
