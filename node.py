# dragondb/node.py
import asyncio
from aiohttp import web
from typing import List
from cluster.migration import DataMigration
from storage.dragonstore.engine_store import DragonStore
from cluster.manager import ClusterManager
from coordinator.coordinator import Coordinator
from api.handlers import Handlers
from models.document import Document
import pickle

class DragonDBNode:
    def __init__(self, node_id: str, all_nodes_info: dict, http_port: int = 8080,
                 data_dir: str = "./data", storage_options: dict = None,
                 cluster_opts: dict = None):
        self.node_id = node_id
        self.all_nodes_info = all_nodes_info
        self.http_port = http_port
        self.data_dir = data_dir
        self.storage_options = storage_options or {}
        self.cluster_opts = cluster_opts or {}

        # 初始化存储引擎
        self.store = DragonStore(data_dir, options=self.storage_options)
        self.storage_adapter = DragonDBStorageAdapter(self.store)  # 适配器

        # 集群管理器
        replication_factor = self.cluster_opts.get('replication_factor', 3)
        self.cluster = ClusterManager(node_id, all_nodes_info, replication_factor)

        # 协调器（传入本地存储和集群管理器）
        self.coordinator = Coordinator(node_id, self.storage_adapter, self.cluster)

        # API 处理器
        self.handlers = Handlers(self.coordinator)

        # 内部 HTTP 应用（与外部 API 共用，稍后在 start 中添加内部路由）
        self.app = None
        self.runner = None
        self.migration = DataMigration(node_id, self.store, self.cluster)
    async def _handle_internal_get(self, request):
        collection = request.match_info['collection']
        doc_id = request.match_info['id']
        doc = await self.storage_adapter.get(collection, doc_id)
        if doc is None:
            return web.json_response(status=404)
        return web.json_response(doc.to_dict())

    async def _handle_internal_put(self, request: web.Request):
        collection = request.match_info['collection']
        doc_id = request.match_info['id']
        try:
            data = await request.json()
        except:
            return web.json_response(status=400)
        doc = Document.from_dict(data)
        success = await self.store.put(collection, doc_id, doc)
        return web.json_response(status=200 if success else 500)

    async def _handle_internal_delete(self, request: web.Request):
        collection = request.match_info['collection']
        doc_id = request.match_info['id']
        success = await self.store.delete(collection, doc_id)
        return web.json_response(status=200 if success else 404)

    async def start(self):
        await self.store.open()
        from api.server import create_app
        self.app = create_app(self.handlers)

        # 内部 RPC 路由
        self.app.router.add_get('/internal/raw/{key}', self._handle_internal_raw_get)
        self.app.router.add_put('/internal/raw/{key}', self._handle_internal_raw_put)
        self.app.router.add_get('/internal/raw/keys', self._handle_internal_raw_keys)
        self.app.router.add_post('/internal/cluster/update', self._handle_internal_cluster_update)

        # 管理路由
        self.app.router.add_post('/admin/cluster/add_node', self._handle_admin_add_node)
        self.app.router.add_post('/admin/cluster/remove_node', self._handle_admin_remove_node)
        self.app.router.add_get('/admin/collections', self._handle_admin_collections)
        self.app.router.add_get('/admin/collections/{collection}/documents', self._handle_admin_collection_documents)

        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host='0.0.0.0', port=self.http_port)
        await site.start()
        self.runner = runner
        print(f"Node {self.node_id} started on port {self.http_port}, data dir: {self.data_dir}")

    async def stop(self):
        # 关闭协调器的 HTTP 客户端
        await self.coordinator.close()
        # 关闭存储
        await self.store.close()
        # 停止 HTTP 服务器
        if self.runner:
            await self.runner.cleanup()

    async def _handle_internal_raw_get(self, request):
        key_hex = request.match_info['key']
        try:
            key = bytes.fromhex(key_hex)
        except ValueError:
            return web.Response(status=400)
        value = await self.store.get(key)
        if value is None:
            return web.Response(status=404)
        return web.Response(body=value)

    async def _handle_internal_raw_put(self, request):
        key_hex = request.match_info['key']
        try:
            key = bytes.fromhex(key_hex)
        except ValueError:
            return web.Response(status=400)
        value = await request.read()
        await self.store.put(key, value)
        return web.Response(status=200)

    async def _handle_internal_raw_keys(self, request):
        """返回所有键的十六进制表示列表"""
        keys = await self.store.get_all_keys()
        hex_keys = [k.hex() for k in keys]
        return web.json_response(hex_keys)

    # 提供手动触发迁移的方法
    async def migrate_data_for_new_node(self, new_node_id: str):
        await self.migration.migrate_data_for_new_node(new_node_id)

    async def migrate_data_for_removed_node(self, removed_node_id: str):
        await self.migration.migrate_data_for_removed_node(removed_node_id)

    async def _handle_internal_cluster_update(self, request):
        data = await request.json()
        action = data['action']
        node_id = data['node_id']
        try:
            if action == 'add_node':
                node_info = data['node_info']
                self.cluster.add_node(node_id, node_info)
            elif action == 'remove_node':
                self.cluster.remove_node(node_id)
            else:
                return web.json_response({'error': 'Unknown action'}, status=400)
        except ValueError as e:
            return web.json_response({'error': str(e)}, status=400)
        return web.json_response({'status': 'success'})

    async def _handle_admin_add_node(self, request):
        data = await request.json()
        new_node_id = data['node_id']
        host = data['host']
        port = data['port']
        data_dir = data.get('data_dir', f"./data/{new_node_id}")
        node_info = {'host': host, 'port': port, 'data_dir': data_dir}
        try:
            self.cluster.add_node(new_node_id, node_info)
        except ValueError as e:
            return web.json_response({'error': str(e)}, status=400)

        # 广播给所有其他节点
        tasks = []
        for node_id in self.cluster.node_ids:
            if node_id == self.node_id or node_id == new_node_id:
                continue
            client = self.coordinator._get_client(node_id)
            if client:
                tasks.append(client.send_cluster_update('add_node', new_node_id, node_info))
        await asyncio.gather(*tasks, return_exceptions=True)

        # 触发数据迁移（异步）
        asyncio.create_task(self.migration.migrate_data_for_new_node(new_node_id))

        return web.json_response({'status': 'success'})

    async def _handle_admin_remove_node(self, request):
        data = await request.json()
        node_id = data['node_id']
        if node_id == self.node_id:
            return web.json_response({'error': 'Cannot remove local node'}, status=400)

        try:
            self.cluster.remove_node(node_id)
        except ValueError as e:
            return web.json_response({'error': str(e)}, status=400)

        # 广播给其他节点（不包括被删除节点）
        tasks = []
        for nid in self.cluster.node_ids:
            if nid == self.node_id:
                continue
            client = self.coordinator._get_client(nid)
            if client:
                tasks.append(client.send_cluster_update('remove_node', node_id))
        await asyncio.gather(*tasks, return_exceptions=True)

        # 触发数据迁移
        asyncio.create_task(self.migration.migrate_data_for_removed_node(node_id))

        return web.json_response({'status': 'success'})

    # 在 node.py 中添加以下方法

    async def _handle_admin_collections(self, request):
        try:
            collections = await self.store.get_all_collections()
            return web.json_response({"collections": collections})
        except Exception as e:
            return web.json_response({"error": f"Failed to get collections: {str(e)}"}, status=500)

    async def _handle_admin_collection_documents(self, request):
        collection = request.match_info['collection']
        try:
            limit = int(request.query.get('limit', 100))
            offset = int(request.query.get('offset', 0))
        except ValueError:
            return web.json_response({"error": "Invalid limit/offset"}, status=400)
        try:
            docs = await self.store.get_documents_by_collection(collection, limit, offset)
            return web.json_response({
                "collection": collection,
                "count": len(docs),
                "offset": offset,
                "limit": limit,
                "documents": [doc.to_dict() for doc in docs]
            })
        except Exception as e:
            return web.json_response({"error": f"Failed to get documents: {str(e)}"}, status=500)

class DragonDBStorageAdapter:
    def __init__(self, store):
        self.store = store

    async def get(self, collection: str, doc_id: str):
        key = f"{collection}:{doc_id}".encode()
        value = await self.store.get(key)
        if value is None:
            return None
        return Document.from_dict(pickle.loads(value))

    async def put(self, collection: str, doc_id: str, document: Document):
        key = f"{collection}:{doc_id}".encode()
        value = pickle.dumps(document.to_dict())
        await self.store.put(key, value)
        return True

    async def delete(self, collection: str, doc_id: str):
        key = f"{collection}:{doc_id}".encode()
        await self.store.delete(key)
        return True

    async def query(self, collection: str, filter_expr: dict, limit: int = 100, offset: int = 0) -> List[Document]:
        """简单查询：仅支持等值过滤，不支持复杂操作符（开发测试用）"""
        # 获取所有键（全表扫描，性能较差，生产环境请勿依赖）
        all_keys = await self.store.get_all_keys()
        docs = []
        for key in all_keys:
            if not key.decode().startswith(f"{collection}:"):
                continue
            value = await self.store.get(key)
            if value is None:
                continue
            doc = Document.from_dict(pickle.loads(value))
            # 简单等值匹配
            match = True
            for field, expected in filter_expr.items():
                # 如果预期值是字典（如 {"$gt":25}），暂时忽略操作符，仅检查字段存在性
                if isinstance(expected, dict):
                    # 暂不支持，跳过该条件
                    continue
                if doc.data.get(field) != expected:
                    match = False
                    break
            if match:
                docs.append(doc)
        # 分页
        return docs[offset:offset + limit]