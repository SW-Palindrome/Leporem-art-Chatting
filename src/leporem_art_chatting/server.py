import asyncio
import logging

import requests
import socketio

from leporem_art_chatting.settings import LOGIN_URL, MESSAGE_UPLOAD_URL, CHATROOM_CREATE_BY_BUYER_URL

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
            'type': data.get('message_type', 'TEXT'),
        }

        response = requests.post(MESSAGE_UPLOAD_URL, data=send_data, headers=headers)
        if response.status_code != 201:
            raise Exception(f'message upload failed with {response.text}')

        await asyncio.gather(
            sio.emit('message_registered', {
                'message_uuid': data['message_uuid'],
                'chat_room_uuid': data['chat_room_uuid'],
            }, room=session['user_id']),
            _send_receive_message(sid, data),
        )


async def _send_receive_message(sid, data):
    async with sio.session(sid) as session:
        if session['user_id'] != data['opponent_user_id']:
            await sio.emit('receive_message', {
                'chat_room_uuid': data['chat_room_uuid'],
                'message': data['message'],
                'message_uuid': data['message_uuid'],
                'message_type': data.get('message_type', 'TEXT'),
            }, room=data['opponent_user_id'])


@sio.event
async def create_chat_room(sid, data):
    await _validate_session_login(sid)
    await _migrate_chat_room(sid, data)


async def _migrate_chat_room(sid, data):
    async with sio.session(sid) as session:
        headers = {
            'Authorization': f'Palindrome {session["id_token"]}',
        }
        send_data = {
            'chat_room_uuid': data['chat_room_uuid'],
            'seller_id': data['seller_id'],
            'text': data['message'],
            'message_uuid': data['message_uuid'],
            'message_type': data.get('message_type', 'TEXT')
        }
        print(send_data)

        response = requests.post(
            CHATROOM_CREATE_BY_BUYER_URL,
            data=send_data,
            headers=headers
        )
        if response.status_code != 201:
            raise Exception(f'chatroom create failed with {response.text}')

        await asyncio.gather(
            sio.emit('chat_room_registered', {
                'chat_room_uuid': data['chat_room_uuid'],
            }, room=session['user_id']),
            # TODO: 채팅방 생성 시 정보 전달
            _send_receive_chat_room(sid, data),
        )


async def _send_receive_chat_room(sid, data):
    async with sio.session(sid) as session:
        if session['user_id'] != data['opponent_user_id']:
            await sio.emit('receive_chat_room_create', {}, room=data['opponent_user_id'])


@sio.event
async def disconnect(sid):
    logger.info(f'disconnect {sid}')


def run_server():
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=80, log_level='info')


if __name__ == '__main__':
    run_server()
