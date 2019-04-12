import inspect
import json
import hashlib

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
    def __init__(self):
        self.methods = {}

        for method_name in DEFAULT_METHODS:
            method = getattr(self, method_name.lower(), None)
            if method:
                self.register_method(method_name, method)
        
    def register_method(self, method_name, method):
        self.methods[method_name.lower()] = method
    
    async def dispatch(self, request: Request):
        method = self.methods.get(request.method.lower())
        if not method:
            raise HTTPMethodNotAllowed('', DEFAULT_METHODS)
        
        wanted_args = list(inspect.signature(method).parameters.keys())
        available_args = request.match_info.copy()
        available_args.update({'request': request})

        unsatisfied_args = set(wanted_args) - set(available_args.keys())
        if unsatisfied_args:
            raise HTTPBadRequest()
        
        return await method(**{arg_name: available_args[arg_name] for arg_name in wanted_args})


class ItemListEndpoint(RestEndpoint):
    def __init__(self, resource):
        super().__init__()
        self.resource = resource

    async def get(self, request) -> Response:
        print(dir(request.__dict__))
        if 'user' in request:
            user_id = request['user'].id
            print(user_id)
            data = json.dumps({
                'items': [item.to_json() for item in session.query(Item).filter(Item.created_by == user_id)]
            }).encode('utf-8')

            return Response(
                status=200,
                body=data,
                content_type='application/json',
            )
        else:
            return Response(
                status=401
            )

    async def post(self, request) -> Response:
        data = await request.json()
        item = Item(data['title'], data['text'], 1)
        session.add(item)
        session.commit()

        data = json.dumps(item.to_json()).encode('utf-8')

        return Response(
            status=201,
            body=data,
            content_type='application/json'
        )


class ItemDetailEndpoint(RestEndpoint):
    def __init__(self, resource):
        super().__init__()
        self.resource = resource
    
    async def get(self, request, pk):
        user_id = request.user.id
        instance = session.query(Item).filter(Item.id == pk, Item.created_by == user_id).first()
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

    async def put(self, request, pk):
        instance = session.query(Item).filter(Item.id == pk).first()

        if not instance:
            return Response(
                status=404,
                body=json.dumps({'not found': 404}),
                content_type='application/json'
            )
        
        data = await request.json()

        instance.title = data['title']
        instance.text = data['text']

        session.add(instance)
        session.commit()

        data = json.dumps(instance.to_json()).encode('utf-8')

        return Response(status=200, body=data, content_type='application/json')

    async def delete(self, pk):
        instance = session.query(Item).filter(Item.id == pk).first()

        if not instance:
            return Response(
                status=404,
                body=json.dumps({'not found': 404}),
                content_type='application/json'
            )

        session.delete(instance)
        session.commit()

        return Response(status=204)


class AuthenticateEndpoint(RestEndpoint):
    def __init__(self, resource):
        super().__init__()
        self.resource = resource

    async def post(self, request):
        data = await request.json()
        email = data['email']
        password = hashlib.sha256(data['password'].encode('utf-8')).hexdigest()

        user = session.query(User).filter(User.email == email, User.password == password).first()

        if user:
            http_session = await get_session(request)
            http_session['user_id'] = user.id
            return Response(status=200)
        else:
            data = json.dumps({'error': 'Bad Authentication data'}).encode('utf-8')
            return Response(status=404, body=data, content_type='application/json')


class RestResource:
    def __init__(
            self,
            verbose_name,
            factory,
            list_endpoint=None,
            detail_endpoint=None,
            common_endpoint=None
        ):
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
            router.add_route('*', '/{}'.format(self.verbose_name), self.list_endpoint.dispatch)
        if hasattr(self, 'detail_endpoint'):
            router.add_route('*', '/{}/{{pk}}'.format(self.verbose_name), self.detail_endpoint.dispatch)
        if hasattr(self, 'common_endpoint'):
            router.add_route('*', '/{}'.format(self.verbose_name), self.common_endpoint.dispatch)