from aiohttp import web
from .handlers import Handlers

def create_app(handlers: Handlers):
    app = web.Application()
    app.router.add_put('/collections/{collection}/documents/{id}', handlers.handle_put_document)
    app.router.add_get('/collections/{collection}/documents/{id}', handlers.handle_get_document)
    app.router.add_delete('/collections/{collection}/documents/{id}', handlers.handle_delete_document)
    app.router.add_post('/collections/{collection}/query', handlers.handle_query)
    return app

async def start_server(handlers: Handlers, host: str = '127.0.0.1', port: int = 8080):
    app = create_app(handlers)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"Server started at http://{host}:{port}")
    return runner