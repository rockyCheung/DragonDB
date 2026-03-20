import json
from aiohttp import web
from models.document import Document
from coordinator.coordinator import Coordinator

class Handlers:
    def __init__(self, coordinator: Coordinator):
        self.coordinator = coordinator

    async def handle_put_document(self, request: web.Request):
        """PUT /collections/{collection}/documents/{id}"""
        collection = request.match_info['collection']
        doc_id = request.match_info['id']
        try:
            data = await request.json()
        except:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        # 可选参数 w
        w = int(request.query.get('w', 2))
        try:
            result = await self.coordinator.write(collection, doc_id, data, w=w)
            return web.json_response(result, status=201)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_get_document(self, request: web.Request):
        """GET /collections/{collection}/documents/{id}"""
        collection = request.match_info['collection']
        doc_id = request.match_info['id']
        r = int(request.query.get('r', 2))
        try:
            result = await self.coordinator.read(collection, doc_id, r=r)
            return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=404 if "None" in str(e) else 500)

    async def handle_delete_document(self, request: web.Request):
        """DELETE /collections/{collection}/documents/{id}"""
        # 简化：仅删除本地，不涉及分布式
        collection = request.match_info['collection']
        doc_id = request.match_info['id']
        # 此处应调用协调器实现分布式删除，暂略
        return web.json_response({"status": "not implemented"}, status=501)

    async def handle_query(self, request: web.Request):
        """POST /collections/{collection}/query"""
        collection = request.match_info['collection']
        try:
            query = await request.json()
        except:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        filter_expr = query.get('filter', {})
        limit = query.get('limit', 100)
        offset = query.get('offset', 0)
        # 查询应在本地存储执行，简化：仅从本地引擎查询
        docs = await self.coordinator.storage.query(collection, filter_expr, limit, offset)
        return web.json_response({"documents": [d.to_dict() for d in docs]})