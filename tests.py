import unittest
import json

from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

from rest import RestResource
from models import Item


class AppTestCase(AioHTTPTestCase):
    def setUp(self):
        self.items = RestResource('items', Item)
        AioHTTPTestCase.setUp(self)

    async def get_application(self):
        app = web.Application()
        self.items.register(app.router)

        return app
    
    @unittest_run_loop
    async def test_get_list_items(self):
        response = await self.client.request('GET', '/items')
        data = await response.json()

        assert response.status == 200
        assert 'items' in data

    @unittest_run_loop
    async def test_get_detail_item(self):
        response = await self.client.request('GET', '/items/1')
        data = await response.json()

        assert response.status == 200
        assert 'id' in data

    @unittest_run_loop
    async def test_add_and_delete_item(self):
        new_item = {
            'title': 'test',
            'text': 'test',
        }

        response = await self.client.request('POST', '/items', data=json.dumps(new_item).encode('utf-8'))
        data = await response.json()

        assert response.status == 201
        assert data['title'] == new_item['title']
        assert data['text'] == new_item['text']

        response = await self.client.request('DELETE', '/items/{}'.format(data['id']))

        assert response.status == 204

        response = await self.client.request('DELETE', '/items/{}'.format(data['id']))

        assert response.status == 404


if __name__ == '__main__':
    unittest.main()