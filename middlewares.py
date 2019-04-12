from aiohttp import web
from aiohttp_session import get_session

from models import User, session


@web.middleware
async def authenticate_middleware(request, handler):
    http_session = await get_session(request)
    print(http_session)
    if 'user_id' in http_session:
        user_id = http_session['user_id']
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            request['user'] = user
    response = await handler(request)
    return response