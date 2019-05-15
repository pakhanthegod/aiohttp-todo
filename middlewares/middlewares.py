import json
import base64
import os

from aiohttp import web
from aiohttp_session import get_session
import jwt

from models.models import User, session


with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json'), encoding='utf-8') as data:
    config = json.load(data)

SECRET_KEY = base64.urlsafe_b64decode(bytes(config['secret_key'], 'utf-8'))


@web.middleware
async def authenticate_middleware(request, handler):
    token = request.cookies.get('JWT_Token', None)
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms='HS256')
            user_id = payload['user_id']
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                request['user'] = user
        except jwt.ExpiredSignatureError:
            data = { 'error': 'Token is expired' }
            body = json.dumps(data)
            response = web.Response(status=401, body=body, content_type='application/json')
            response.del_cookie('JWT_Token')
            return response
    response = await handler(request)
    return response