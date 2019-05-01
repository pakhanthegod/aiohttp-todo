import inspect
import json
import bcrypt
import html

from aiohttp.web import Request, Response
from aiohttp.web import get, post, put, delete
from aiohttp.web import Application, run_app
from aiohttp.web import HTTPMethodNotAllowed, HTTPBadRequest
from aiohttp.web import UrlDispatcher
from aiohttp_session import get_session
from sqlalchemy import inspect as sql_inspect

from models import User, Item, session


DEFAULT_METHODS = ('GET', 'POST', 'PUT', 'DELETE')


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
                    body=json.dumps({'not found': 404}),
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
                    body=json.dumps({'not found': 404}),
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
                    body=json.dumps({'not found': 404}),
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
        password = html.escape(data['password'])

        user = session.query(self.user_factory).filter(
            self.user_factory.email == email
        ).first()
        hashed_password = user.password or None

        if hashed_password and bcrypt.hashpw(password, hashed_password) == hashed_password:
            http_session = await get_session(request)
            http_session['user_id'] = user.id

            return Response(status=200)
        else:
            data = json.dumps(
                { 'error': 'Bad Authentication data' }
            ).encode('utf-8')

            return Response(status=404, body=data, content_type='application/json')


class RestResource:
    """
    Class that registers endpoints to paths.
    """
    def __init__(
        self,
        verbose_name,
        factory,
        list_endpoint=None,
        detail_endpoint=None,
        common_endpoint=None
    ):
        """
        versbose_name is used for create a path,
        factory is used for provide a factory of object to an endpoint
        """
        self.verbose_name = verbose_name
        self.factory = factory

        if list_endpoint:
            self.list_endpoint = list_endpoint(self)
        if detail_endpoint:
            self.detail_endpoint = detail_endpoint(self)
        if common_endpoint:
            self.common_endpoint = common_endpoint(self)

    def register(self, router: UrlDispatcher):
        if hasattr(self, 'list_endpoint'):
            router.add_route('*', '/{}'.format(self.verbose_name),
                             self.list_endpoint.dispatch)
        if hasattr(self, 'detail_endpoint'):
            router.add_route(
                '*', '/{}/{{pk}}'.format(self.verbose_name), self.detail_endpoint.dispatch)
        if hasattr(self, 'common_endpoint'):
            router.add_route('*', '/{}'.format(self.verbose_name),
                             self.common_endpoint.dispatch)
