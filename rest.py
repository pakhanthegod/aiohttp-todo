import inspect
import json

from aiohttp.web import Request, Response
from aiohttp.web import get, post, put, delete
from aiohttp.web import Application, run_app
from aiohttp.web import HTTPMethodNotAllowed, HTTPBadRequest
from aiohttp.web import UrlDispatcher
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

    async def get(self) -> Response:
        data = json.dumps({
            'items': [item.to_json() for item in session.query(Item)]
        }).encode('utf-8')

        return Response(
            status=200,
            body=data,
            content_type='application/json',
        )

    async def post(self, request) -> Response:
        data = await request.json()
        item = Item(data['title'], data['text'], 1)
        session.add(item)
        session.commit()
        return Response(status=200)


class ItemDetailEndpoint(RestEndpoint):
    def __init__(self, resource):
        super().__init__()
        self.resource = resource
    
    async def get(self, pk):
        instance = session.query(Item).filter(Item.id == pk).first()
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

        return Response(status=201, body=data, content_type='application/json')

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


class RestResource:
    def __init__(self, verbose_name, factory):
        self.verbose_name = verbose_name
        self.factory = factory

        self.items_endpoint = ItemListEndpoint(self)
        self.item_detail_endpoint = ItemDetailEndpoint(self)
    
    def register(self, router: UrlDispatcher):
        router.add_route('*', '/{}'.format(self.verbose_name), self.items_endpoint.dispatch)
        router.add_route('*', '/{}/{{pk}}'.format(self.verbose_name), self.item_detail_endpoint.dispatch)