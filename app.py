import base64
import json

from cryptography import fernet
from aiohttp.web import Application, run_app
from aiohttp_session import setup, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from rest import (
    RestResource,
    ItemListEndpoint,
    ItemDetailEndpoint,
    AuthenticateEndpoint,
)
from models import Item, User
from middlewares import authenticate_middleware

app = Application()

with open('config.json', encoding='utf-8') as data:
    config = json.load(data)

secret_key = base64.urlsafe_b64decode(bytes(config['secret_key'], 'utf-8'))

setup(app, EncryptedCookieStorage(secret_key))
app.middlewares.append(authenticate_middleware)

item_resource = RestResource(
    'items',
    Item,
    list_endpoint=ItemListEndpoint,
    detail_endpoint=ItemDetailEndpoint,
)
item_resource.register(app.router)

auth_resource = RestResource(
    'auth',
    User,
    common_endpoint=AuthenticateEndpoint,
)
auth_resource.register(app.router)

if __name__ == '__main__':
    run_app(app, host='localhost', port=8000)