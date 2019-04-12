import base64

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
fernet_key = fernet.Fernet.generate_key()
secret_key = base64.urlsafe_b64decode(fernet_key)

setup(app, EncryptedCookieStorage(secret_key))
app.middlewares.append(authenticate_middleware)

item_resource = RestResource(
    'items',
    Item,
    list_endpoint=ItemListEndpoint,
    detail_endpoint=ItemDetailEndpoint
)
item_resource.register(app.router)

auth_resource = RestResource(
    'auth',
    User,
    common_endpoint=AuthenticateEndpoint
)
auth_resource.register(app.router)

if __name__ == '__main__':
    run_app(app, host='localhost', port=8000)