import inspect
import json

from aiohttp.web import Request, Response
from aiohttp.web import get, post, put, delete
from aiohttp.web import Application, run_app
from aiohttp.web import HTTPMethodNotAllowed, HTTPBadRequest
from aiohttp.web import UrlDispatcher

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
        print(request.method.upper(), self.methods)
        if not method:
            raise HTTPMethodNotAllowed('', DEFAULT_METHODS)
        
        wanted_args = list(inspect.signature(method).parameters.keys())
        available_args = request.match_info.copy()
        available_args.update({'request': request})

        unsatisfied_args = set(wanted_args) - set(available_args.keys())
        if unsatisfied_args:
            raise HTTPBadRequest()
        
        return await method(**{arg_name: available_args[arg_name] for arg_name in wanted_args})


class ItemsListEndpoint(RestEndpoint):
    def __init__(self, resource):
        super().__init__()
        self.resource = resource

    async def get(self) -> Response:
        return Response(
            status=200,
            body=json.dumps({
                'items': [
                    {
                        'id': item.id,
                        'title': item.title,
                        'text': item.text,
                        'created_at': item.created_at.isoformat(),
                        'created_by': item.created_by,
                        'owner': item.owner.id,
                    }
                    for item in session.query(Item)
                ]
            }),
            content_type='application/json',
        )


class RestResource:
    def __init__(self, verbose_name, factory):
        self.verbose_name = verbose_name
        self.factory = factory

        self.items_endpoint = ItemsListEndpoint(self)
    
    def register(self, router: UrlDispatcher):
        router.add_route('*', '/{}'.format(self.verbose_name), self.items_endpoint.dispatch)