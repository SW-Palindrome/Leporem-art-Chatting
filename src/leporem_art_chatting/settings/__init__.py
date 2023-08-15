import os

if os.getenv('ENV') == 'dev':
    from .develop import *
elif os.getenv('ENV') == 'prod':
    from .production import *

LOGIN_URL = BASE_API_URL + '/users/info/my'
MESSAGE_UPLOAD_URL = BASE_API_URL + '/chats/messages'
CHATROOM_CREATE_BY_BUYER_URL = BASE_API_URL + '/chats/buyer'
