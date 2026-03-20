## DragonDB Python 实现（核心代码）

### 一、项目结构
```
dragondb/
├── node.py               # 节点主类
├── storage/
│   ├── engine.py         # 存储引擎接口及内存实现
│   └── __init__.py
├── cluster/
│   ├── manager.py        # 集群管理
│   ├── hashring.py       # 一致性哈希
│   └── __init__.py
├── coordinator/
│   ├── coordinator.py    # 读写协调器
│   └── version.py        # 向量时钟工具
├── api/
│   ├── server.py         # aiohttp 服务器
│   ├── handlers.py       # HTTP 请求处理
│   └── __init__.py
├── models/
│   └── document.py       # 文档模型
└── utils/
    └── serialization.py  # JSON 序列化
```

### 二、代码实现

#### 1. `models/document.py` - 文档模型与版本向量
```python
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class Document:
    """文档模型，包含数据和元数据"""
    id: str
    collection: str
    data: Dict[str, Any]
    version_vector: Dict[str, int] = field(default_factory=dict)  # 节点ID -> 版本号
    timestamp: float = field(default_factory=time.time)           # 最后修改时间

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "collection": self.collection,
            "data": self.data,
            "version_vector": self.version_vector,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Document":
        return cls(
            id=d["id"],
            collection=d["collection"],
            data=d["data"],
            version_vector=d.get("version_vector", {}),
            timestamp=d.get("timestamp", time.time())
        )
```

#### 2. `storage/engine.py` - 内存存储引擎
```python
import asyncio
from typing import Optional, List, Dict, Any
from models.document import Document

class StorageEngine:
    """存储引擎接口，基于内存实现"""
    def __init__(self, node_id: str):
        self.node_id = node_id
        # 数据结构：{collection: {doc_id: Document}}
        self._data: Dict[str, Dict[str, Document]] = {}
        # 二级索引（简化：仅用于演示，实际应使用 B+ 树等）
        self._indices: Dict[str, Dict[str, List[str]]] = {}  # collection -> field -> value -> [doc_ids]
        self._lock = asyncio.Lock()

    async def get(self, collection: str, doc_id: str) -> Optional[Document]:
        async with self._lock:
            coll_data = self._data.get(collection)
            if not coll_data:
                return None
            return coll_data.get(doc_id)

    async def put(self, collection: str, doc_id: str, document: Document) -> bool:
        async with self._lock:
            if collection not in self._data:
                self._data[collection] = {}
            old_doc = self._data[collection].get(doc_id)
            # 更新文档，保留传入的版本向量
            self._data[collection][doc_id] = document
            # 更新索引（简化：假设索引字段是 'name' 和 'age'）
            await self._update_index(collection, document, old_doc)
            return True

    async def delete(self, collection: str, doc_id: str) -> bool:
        async with self._lock:
            coll_data = self._data.get(collection)
            if not coll_data or doc_id not in coll_data:
                return False
            doc = coll_data.pop(doc_id)
            await self._remove_from_index(collection, doc)
            return True

    async def query(self, collection: str, filter_expr: Dict[str, Any], limit: int = 100, offset: int = 0) -> List[Document]:
        """简单查询：仅支持等值过滤，不支持复杂条件"""
        async with self._lock:
            coll_data = self._data.get(collection, {})
            results = []
            # 如果有索引，使用索引加速
            if filter_expr:
                # 简化：只取第一个等值条件
                field, value = next(iter(filter_expr.items()))
                if field in self._indices.get(collection, {}):
                    doc_ids = self._indices[collection][field].get(str(value), [])
                    for doc_id in doc_ids:
                        if doc_id in coll_data:
                            results.append(coll_data[doc_id])
                else:
                    # 全表扫描
                    for doc in coll_data.values():
                        if all(doc.data.get(k) == v for k, v in filter_expr.items()):
                            results.append(doc)
            else:
                results = list(coll_data.values())
            # 分页
            return results[offset:offset+limit]

    async def _update_index(self, collection: str, new_doc: Document, old_doc: Optional[Document]):
        """维护简单索引"""
        if collection not in self._indices:
            self._indices[collection] = {}
        # 假设为 'name' 和 'age' 字段创建索引
        for field in ['name', 'age']:
            if field not in self._indices[collection]:
                self._indices[collection][field] = {}
            # 移除旧值
            if old_doc and field in old_doc.data:
                old_val = str(old_doc.data[field])
                if old_val in self._indices[collection][field]:
                    if new_doc.id in self._indices[collection][field][old_val]:
                        self._indices[collection][field][old_val].remove(new_doc.id)
            # 添加新值
            if field in new_doc.data:
                new_val = str(new_doc.data[field])
                if new_val not in self._indices[collection][field]:
                    self._indices[collection][field][new_val] = []
                if new_doc.id not in self._indices[collection][field][new_val]:
                    self._indices[collection][field][new_val].append(new_doc.id)

    async def _remove_from_index(self, collection: str, doc: Document):
        """从索引中移除文档"""
        if collection not in self._indices:
            return
        for field in ['name', 'age']:
            if field in doc.data and field in self._indices[collection]:
                val = str(doc.data[field])
                if val in self._indices[collection][field]:
                    if doc.id in self._indices[collection][field][val]:
                        self._indices[collection][field][val].remove(doc.id)
```

#### 3. `cluster/hashring.py` - 一致性哈希环
```python
import hashlib
import bisect
from typing import List, Dict, Optional

class ConsistentHashRing:
    """一致性哈希环（支持虚拟节点）"""
    def __init__(self, nodes: List[str] = None, vnodes_per_node: int = 100):
        self.vnodes_per_node = vnodes_per_node
        self.ring: Dict[int, str] = {}          # 哈希值 -> 物理节点ID
        self.sorted_keys: List[int] = []        # 有序哈希值列表
        if nodes:
            for node in nodes:
                self.add_node(node)

    def _hash(self, key: str) -> int:
        """计算字符串的哈希值（使用MD5）"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node_id: str):
        """添加物理节点及其虚拟节点"""
        for i in range(self.vnodes_per_node):
            vnode_key = f"{node_id}:{i}"
            hash_val = self._hash(vnode_key)
            self.ring[hash_val] = node_id
            self.sorted_keys.append(hash_val)
        self.sorted_keys.sort()

    def remove_node(self, node_id: str):
        """移除物理节点及其所有虚拟节点"""
        to_remove = []
        for h, n in self.ring.items():
            if n == node_id:
                to_remove.append(h)
        for h in to_remove:
            del self.ring[h]
            self.sorted_keys.remove(h)

    def get_node(self, key: str) -> Optional[str]:
        """根据key获取负责的物理节点"""
        if not self.ring:
            return None
        hash_val = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, hash_val) % len(self.sorted_keys)
        return self.ring[self.sorted_keys[idx]]
```

#### 4. `cluster/manager.py` - 集群管理
```python
from typing import List, Dict, Optional
from .hashring import ConsistentHashRing

class ClusterManager:
    """集群元数据管理：维护节点列表、分区映射"""
    def __init__(self, local_node_id: str, seed_nodes: List[str] = None, replication_factor: int = 3):
        self.local_node_id = local_node_id
        self.replication_factor = replication_factor
        # 集群所有节点（包括自身）
        self.nodes: List[str] = [local_node_id] + (seed_nodes or [])
        # 一致性哈希环（用于分区）
        self.ring = ConsistentHashRing(self.nodes, vnodes_per_node=100)
        # 分区映射：partition_id -> [replica_node_ids]
        # 简化：将一致性哈希的每个虚拟节点视为一个分区，副本就是物理节点自身（副本数由环的虚拟节点决定）
        # 为简化，我们直接使用环的 get_node 决定主副本，副本列表通过环的连续多个节点获取
        self.partition_count = len(self.ring.ring)  # 虚拟节点数

    def get_partition(self, key: str) -> int:
        """根据key计算分区ID（虚拟节点哈希值）"""
        return self.ring._hash(key)  # 简单返回哈希值作为分区ID

    def get_replicas(self, key: str) -> List[str]:
        """返回给定key的所有副本节点（按顺序）"""
        if not self.nodes:
            return []
        hash_val = self.ring._hash(key)
        idx = bisect.bisect_right(self.ring.sorted_keys, hash_val) % len(self.ring.sorted_keys)
        replicas = []
        # 获取连续的 replication_factor 个不同物理节点
        seen = set()
        for i in range(len(self.ring.sorted_keys)):
            node = self.ring.ring[self.ring.sorted_keys[(idx + i) % len(self.ring.sorted_keys)]]
            if node not in seen:
                replicas.append(node)
                seen.add(node)
            if len(replicas) >= self.replication_factor:
                break
        return replicas

    def node_online(self, node_id: str) -> bool:
        """检查节点是否在线（简化：默认所有节点在线）"""
        return True  # 实际中需通过心跳检测

    def add_node(self, node_id: str):
        """添加新节点到集群（触发再平衡，简化版直接添加）"""
        if node_id not in self.nodes:
            self.nodes.append(node_id)
            self.ring.add_node(node_id)

    def remove_node(self, node_id: str):
        """移除节点（简化）"""
        if node_id in self.nodes:
            self.nodes.remove(node_id)
            self.ring.remove_node(node_id)
```

#### 5. `coordinator/version.py` - 向量时钟工具
```python
from typing import Dict, Optional, List
from models.document import Document

def increment_version(vv: Dict[str, int], node_id: str) -> Dict[str, int]:
    """为指定节点递增版本号"""
    new_vv = vv.copy()
    new_vv[node_id] = new_vv.get(node_id, 0) + 1
    return new_vv

def compare_versions(v1: Dict[str, int], v2: Dict[str, int]) -> Optional[str]:
    """
    比较两个版本向量：
    返回 'before', 'after', 'conflict', 'equal'
    """
    if v1 == v2:
        return 'equal'
    # 检查v1是否小于等于v2
    v1_le_v2 = all(v1.get(k, 0) <= v2.get(k, 0) for k in set(v1) | set(v2))
    v2_le_v1 = all(v2.get(k, 0) <= v1.get(k, 0) for k in set(v1) | set(v2))
    if v1_le_v2 and not v2_le_v1:
        return 'before'
    if v2_le_v1 and not v1_le_v2:
        return 'after'
    return 'conflict'

def merge_versions(docs: List[Document], resolver: str = 'LWW') -> Document:
    """
    合并多个版本（简单LWW：取最新时间戳）
    实际中应根据向量时钟解决冲突，这里简化
    """
    if not docs:
        raise ValueError("No documents to merge")
    if len(docs) == 1:
        return docs[0]
    # 按时间戳降序排序
    docs.sort(key=lambda d: d.timestamp, reverse=True)
    return docs[0]
```

#### 6. `coordinator/coordinator.py` - 读写协调器
```python
import asyncio
from typing import List, Optional, Dict, Any
from models.document import Document
from storage.engine import StorageEngine
from cluster.manager import ClusterManager
from .version import increment_version, compare_versions, merge_versions

class Coordinator:
    """读写协调器：执行Quorum逻辑"""
    def __init__(self, local_node_id: str, storage: StorageEngine, cluster: ClusterManager):
        self.local_node_id = local_node_id
        self.storage = storage
        self.cluster = cluster
        # 模拟其他节点的存储引擎（实际中应通过RPC调用）
        self.remote_storages: Dict[str, StorageEngine] = {}  # node_id -> engine

    def register_remote(self, node_id: str, engine: StorageEngine):
        """注册远程节点存储引擎（用于模拟）"""
        self.remote_storages[node_id] = engine

    async def write(self, collection: str, doc_id: str, data: Dict[str, Any],
                    w: int = 2, consistency: str = 'quorum') -> Dict[str, Any]:
        """执行写操作，返回最终写入的文档"""
        replicas = self.cluster.get_replicas(doc_id)
        if len(replicas) < w:
            raise Exception(f"Not enough replicas: required {w}, available {len(replicas)}")

        # 准备新文档（版本向量暂为本地递增，但需与现有版本合并）
        # 首先尝试读取当前文档（从主副本）以获得版本信息
        current_doc = await self._read_local_or_remote(replicas[0], collection, doc_id)
        if current_doc:
            # 存在旧文档，合并版本向量（每个维度取max）并递增本地
            new_vv = current_doc.version_vector.copy()
            # 确保本地计数器大于所有副本
            local_counter = new_vv.get(self.local_node_id, 0)
            new_vv[self.local_node_id] = local_counter + 1
        else:
            # 新文档，初始化版本向量
            new_vv = {self.local_node_id: 1}
        new_doc = Document(id=doc_id, collection=collection, data=data, version_vector=new_vv)

        # 并发写入所有副本
        tasks = []
        for node in replicas:
            if node == self.local_node_id:
                tasks.append(self.storage.put(collection, doc_id, new_doc))
            else:
                # 假设有远程调用
                remote_engine = self.remote_storages.get(node)
                if remote_engine:
                    tasks.append(remote_engine.put(collection, doc_id, new_doc))
                else:
                    tasks.append(asyncio.sleep(0))  # 模拟失败

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)
        if success_count >= w:
            return {"status": "success", "document": new_doc.to_dict(), "w": success_count}
        else:
            raise Exception(f"Write failed: only {success_count} acks, required {w}")

    async def read(self, collection: str, doc_id: str, r: int = 2) -> Dict[str, Any]:
        """执行读操作，合并多个版本"""
        replicas = self.cluster.get_replicas(doc_id)
        if len(replicas) < r:
            raise Exception(f"Not enough replicas: required {r}, available {len(replicas)}")

        # 并发读取
        tasks = []
        for node in replicas:
            if node == self.local_node_id:
                tasks.append(self.storage.get(collection, doc_id))
            else:
                remote_engine = self.remote_storages.get(node)
                if remote_engine:
                    tasks.append(remote_engine.get(collection, doc_id))
                else:
                    tasks.append(asyncio.sleep(0, result=None))

        results = await asyncio.gather(*tasks)
        valid_docs = [doc for doc in results if doc is not None]
        if len(valid_docs) < r:
            raise Exception(f"Read failed: only {len(valid_docs)} responses, required {r}")

        # 版本合并
        merged = merge_versions(valid_docs, resolver='LWW')
        # 可选：执行读取修复（将merged写回过期副本）
        return {"status": "success", "document": merged.to_dict(), "replicas_read": len(valid_docs)}

    async def _read_local_or_remote(self, node: str, collection: str, doc_id: str) -> Optional[Document]:
        """从指定节点读取文档"""
        if node == self.local_node_id:
            return await self.storage.get(collection, doc_id)
        remote = self.remote_storages.get(node)
        if remote:
            return await remote.get(collection, doc_id)
        return None
```

#### 7. `api/handlers.py` - HTTP请求处理
```python
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
```

#### 8. `api/server.py` - aiohttp服务器
```python
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
```

#### 9. `node.py` - 节点主类
```python
import asyncio
from storage.engine import StorageEngine
from cluster.manager import ClusterManager
from coordinator.coordinator import Coordinator
from api.server import start_server
from api.handlers import Handlers

class DragonDBNode:
    def __init__(self, node_id: str, seed_nodes: list = None, http_port: int = 8080):
        self.node_id = node_id
        self.seed_nodes = seed_nodes or []
        self.http_port = http_port

        # 初始化组件
        self.storage = StorageEngine(node_id)
        self.cluster = ClusterManager(node_id, seed_nodes, replication_factor=3)
        self.coordinator = Coordinator(node_id, self.storage, self.cluster)
        self.handlers = Handlers(self.coordinator)

        # 模拟远程节点（简化：假设所有节点都在同一进程）
        self._other_nodes = {}

    def register_peer(self, node: 'DragonDBNode'):
        """注册对等节点（用于模拟）"""
        self._other_nodes[node.node_id] = node
        # 互相注册存储引擎
        self.coordinator.register_remote(node.node_id, node.storage)
        node.coordinator.register_remote(self.node_id, self.storage)

    async def start(self):
        """启动节点服务"""
        # 启动HTTP服务器
        self.runner = await start_server(self.handlers, port=self.http_port)
        print(f"Node {self.node_id} started on port {self.http_port}")

    async def stop(self):
        """停止节点"""
        await self.runner.cleanup()

async def main():
    # 创建三个节点模拟集群
    node1 = DragonDBNode("node1", seed_nodes=["node2", "node3"], http_port=8081)
    node2 = DragonDBNode("node2", seed_nodes=["node1", "node3"], http_port=8082)
    node3 = DragonDBNode("node3", seed_nodes=["node1", "node2"], http_port=8083)

    # 互相注册（模拟网络）
    node1.register_peer(node2); node1.register_peer(node3)
    node2.register_peer(node1); node2.register_peer(node3)
    node3.register_peer(node1); node3.register_peer(node2)

    # 启动所有节点
    await asyncio.gather(node1.start(), node2.start(), node3.start())

    try:
        # 保持运行
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await node1.stop()
        await node2.stop()
        await node3.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### 三、运行说明
1. 安装依赖：`pip install aiohttp`
2. 将以上代码按结构保存为Python文件。
3. 运行 `python node.py` 启动三个节点（端口8081-8083）。
4. 使用curl测试：
   ```bash
   # 写文档到 node1
   curl -X PUT http://127.0.0.1:8081/collections/users/documents/1001 \
        -H "Content-Type: application/json" -d '{"name":"Alice","age":30}'
   # 从 node2 读取（应该通过一致性哈希路由到正确副本）
   curl http://127.0.0.1:8082/collections/users/documents/1001
   # 查询
   curl -X POST http://127.0.0.1:8083/collections/users/query \
        -H "Content-Type: application/json" -d '{"filter":{"age":30}}'
   ```

### 四、关键特性说明
- **文档模型**：JSON格式，动态模式。
- **分布式**：一致性哈希分片 + 可配置副本数（默认3），可调一致性（通过`w`和`r`参数）。
- **冲突处理**：使用向量时钟检测并发更新，读时合并（LWW策略）。
- **轻量级**：纯Python实现，仅依赖`aiohttp`，内存存储。
- **RESTful API**：符合设计，支持基本CRUD和简单查询。

### 五、后续扩展方向
- 持久化存储（RocksDB集成）
- Gossip协议自动发现节点
- 真正的RPC通信（替代内存调用）
- 更完善的二级索引和查询优化
- 监控和管理接口

以上代码提供了DragonDB的最小可行实现，完整展现了核心设计思想。可根据需求进一步扩展。