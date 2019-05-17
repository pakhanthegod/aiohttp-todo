import inspect
import json
import html
import datetime
import base64
import os

import jwt
import bcrypt
import aiohttp_cors
from validate_email import validate_email
from aiohttp.web import Request, Response
from aiohttp.web import get, post, put, delete
from aiohttp.web import Application, run_app
from aiohttp.web import HTTPMethodNotAllowed, HTTPBadRequest
from aiohttp.web import UrlDispatcher
from aiohttp_session import get_session
from sqlalchemy import inspect as sql_inspect
from sqlalchemy.exc import IntegrityError

from models.models import User, Item, session


DEFAULT_METHODS = ('GET', 'POST', 'PUT', 'DELETE')


with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json'), encoding='utf-8') as data:
    config = json.load(data)

SECRET_KEY = base64.urlsafe_b64decode(bytes(config['secret_key'], 'utf-8'))


class RestEndpoint:
    """
    Base abstract class for endpoints which registers methods
    and dispatches to them.
    """
    def __init__(self):
        self.methods = {}

        for method_name in DEFAULT_METHODS:
            # If a method exists in a subclass so It will be registered
            method = getattr(self, method_name.lower(), None)

            if method:
                self.register_method(method_name, method)

    def register_method(self, method_name, method):
        """
        Register a method in a dict object by its name.
        """
        self.methods[method_name.lower()] = method

    async def dispatch(self, request: Request):
        """
        Dispatch a request to a required method and pass the arguments in it.
        """
        method = self.methods.get(request.method.lower())

        if not method:
            raise HTTPMethodNotAllowed('', DEFAULT_METHODS)

        # Get required args that are needed to the method
        wanted_args = list(inspect.signature(method).parameters.keys())
        # Get retrieved args from request
        available_args = request.match_info.copy()
        # Add the required request arg to the retrieved args 
        available_args.update({'request': request})
        unsatisfied_args = set(wanted_args) - set(available_args.keys())

        if unsatisfied_args:
            raise HTTPBadRequest()

        return await method(**{arg_name: available_args[arg_name] for arg_name in wanted_args})


class ItemListEndpoint(RestEndpoint):
    """
    List endpoint of Item object.

    GET: return the list of Item objects
    POST: create a new Item object
    """
    def __init__(self, resource):
        super().__init__()
        self.resource = resource
        self.item_factory = resource.factory

    async def get(self, request) -> Response:
        if 'user' in request:
            user_id = request['user'].id
            data = json.dumps({
                'items': [
                    item.to_json() for item in session.query(self.item_factory).filter(
                        self.item_factory.created_by == user_id
                    )
                ]
            }).encode('utf-8')

            return Response(
                status=200,
                body=data,
                content_type='application/json',
            )
        else:
            return Response(status=401)

    async def post(self, request) -> Response:
        if 'user' in request:
            user_id = request['user'].id
            data = await request.json()
            title = html.escape(data['title'])
            text = html.escape(data['text'])

            item = self.item_factory(title, text, user_id)
            data = json.dumps(item.to_json()).encode('utf-8')

            session.add(item)
            session.commit()

            return Response(
                status=201,
                body=data,
                content_type='application/json'
            )
        else:
            return Response(status=401)


class ItemDetailEndpoint(RestEndpoint):
    """
    Detail endpoint of Item object.

    GET: return the Item object
    PUT: update the Item object by passing data
    DELETE: delete the Item object
    """
    def __init__(self, resource):
        super().__init__()
        self.item_factory = resource.factory

    async def get(self, request, pk):
        if 'user' in request:
            user_id = request['user'].id
            instance = session.query(self.item_factory).filter(
                self.item_factory.id == pk,
                self.item_factory.created_by == user_id
            ).first()

            if not instance:
                return Response(
                    status=404,
                    body=json.dumps({ 'not found': 404 }),
                    content_type='application/json'
                )

            data = json.dumps(instance.to_json()).encode('utf-8')

            return Response(
                status=200,
                body=data,
                content_type='application/json'
            )
        else:
            return Response(status=401)

    async def put(self, request, pk):
        if 'user' in request:
            user_id = request['user'].id
            instance = session.query(self.item_factory).filter(
                self.item_factory.id == pk,
                self.item_factory.created_by == user_id
            ).first()

            if not instance:
                return Response(
                    status=404,
                    body=json.dumps({ 'not found': 404} ),
                    content_type='application/json'
                )

            data = await request.json()

            instance.title = html.escape(data['title'])
            instance.text = html.escape(data['text'])

            session.add(instance)
            session.commit()

            data = json.dumps(instance.to_json()).encode('utf-8')

            return Response(status=200, body=data, content_type='application/json')
        else:
            return Response(status=401)

    async def delete(self, request, pk):
        if 'user' in request:
            user_id = request['user'].id
            instance = session.query(self.item_factory).filter(
                self.item_factory.id == pk,
                self.item_factory.created_by == user_id
            ).first()

            if not instance:
                return Response(
                    status=404,
                    body=json.dumps({ 'not found': 404 }),
                    content_type='application/json'
                )

            session.delete(instance)
            session.commit()

            return Response(status=204)
        else:
            return Response(status=401)


class AuthenticateEndpoint(RestEndpoint):
    """
    Authenticate endpoint which authenticates a user.

    POST: authenticate a user in write user_id in the session.
    """
    def __init__(self, resource):
        super().__init__()
        self.user_factory = resource.factory

    async def post(self, request):
        data = await request.json()
        email = html.escape(data['email'])
        password = html.escape(data['password']).encode('utf-8')  # Encode for bcrypt
        print(email, password)
        user = session.query(self.user_factory).filter(
            self.user_factory.email == email
        ).first()
        if user:
            hashed_password = user.password
        else:
            data = json.dumps({ 'msg': 'Bad authentication data' })

            return Response(status=400, body=data, content_type='application/json')

        if bcrypt.hashpw(password, hashed_password) == hashed_password:
            payload = {
                'user_id': user.id,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=48)
            }
            token = jwt.encode(payload, SECRET_KEY, algorithm='HS256').decode('utf-8')
            data = json.dumps({ 'msg': 'Authenticated' })
            response = Response(status=200, body=data, content_type='application/json')
            response.set_cookie('JWT_Token', token, httponly=True, secure=False)  # Secure is false, because Postman doesn't support it

            return response
        else:
            data = json.dumps({ 'msg': 'Bad authentication ata' })

            return Response(status=400, body=data, content_type='application/json')


class RegisterEndpoint(RestEndpoint):
    """
    Register new users.

    POST: register a new user.
    """
    def __init__(self, resource):
        super().__init__()
        self.user_factory = resource.factory

    async def post(self, request):
        data = await request.json()
        email = html.escape(data['email'])
        password = html.escape(data['password']).encode('utf-8')  # Encode for bcrypt
        password1 = html.escape(data['password1']).encode('utf-8')

        if validate_email(email):
            if password == password1:
                try:
                    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
                    new_user = User(email=email, password=hashed_password)
                    session.add(new_user)
                    session.commit()
                    return Response(status=201)
                except IntegrityError:
                    session.rollback()
                    data = { 'error': 'Email is not unique' }
                    body = json.dumps(data)
                    return Response(status=400, body=body, content_type='application/json')
            else:
                data = { 'error': 'Passwords are not equal' }
                body = json.dumps(data)
                return Response(status=400, body=body, content_type='application/json')
        else:
            data = { 'error': 'Email is not correct' }
            body = json.dumps(data)
            return Response(status=400, body=body, content_type='application/json')


class RestResource:
    """
    Class that registers endpoints to paths.
    """
    def __init__(
        self,
        url,
        factory,
        endpoint,
        app,
    ):
        """
        `url` is used for create a path,
        `factory` is used for provide a factory of object to an endpoint
        """
        self.factory = factory
        self.url = url
        self.endpoint = endpoint(self)
        self.app = app
        # CORS settings
        self.cors = aiohttp_cors.setup(app, defaults={
            '*': aiohttp_cors.ResourceOptions(
                expose_headers='*',
                allow_headers='*',
                allow_methods='*',
                allow_credentials=True,
            )
        })


    def register(self):
        """
        Register a URL to handler.
        """
        resource = self.cors.add(self.app.router.add_resource(self.url))
        self.cors.add(resource.add_route('*', self.endpoint.dispatch))
