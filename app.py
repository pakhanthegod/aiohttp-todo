import base64
import json

from cryptography import fernet
from aiohttp.web import Application, run_app
from aiohttp_session import setup, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from views.rest import (
    RestResource,
    ItemListEndpoint,
    ItemDetailEndpoint,
    AuthenticateEndpoint,
    RegisterEndpoint
)
from models.models import User, Item
from middlewares.middlewares import authenticate_middleware

app = Application()

with open('config.json', encoding='utf-8') as data:
    config = json.load(data)

SECRET_KEY = base64.urlsafe_b64decode(bytes(config['secret_key'], 'utf-8'))

setup(app, EncryptedCookieStorage(SECRET_KEY))
app.middlewares.append(authenticate_middleware)

items_list_resource = RestResource(
    '/items',
    Item,
    ItemListEndpoint,
)
items_list_resource.register(app.router)

item_detail_resource = RestResource(
    '/items/{pk}',
    Item,
    ItemDetailEndpoint,
)

auth_resource = RestResource(
    '/auth',
    User,
    AuthenticateEndpoint,
)
auth_resource.register(app.router)

register_resource = RestResource(
    '/register',
    User,
    RegisterEndpoint,
)
register_resource.register(app.router)

if __name__ == '__main__':
    run_app(app, host='localhost', port=8000)