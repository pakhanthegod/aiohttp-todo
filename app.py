from aiohttp.web import Application, run_app

from rest import RestResource
from models import Item

app = Application()
item_resource = RestResource('items', Item)
item_resource.register(app.router)

if __name__ == '__main__':
    run_app(app, host='localhost', port=8000)