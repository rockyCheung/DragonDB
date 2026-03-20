# dragondb/coordinator/coordinator.py
import asyncio
from typing import List, Dict, Any
from models.document import Document
from cluster.manager import ClusterManager
from .version import merge_versions
from .remote_client import RemoteStorageClient

class Coordinator:
    def __init__(self, local_node_id: str, local_storage, cluster_manager: ClusterManager):
        self.local_node_id = local_node_id
        self.storage = local_storage
        self.cluster = cluster_manager
        self.clients: Dict[str, RemoteStorageClient] = {}  # node_id -> client

    def _get_client(self, node_id: str) -> RemoteStorageClient:
        if node_id == self.local_node_id:
            # 本地节点不走 HTTP，直接使用 local_storage
            return None
        if node_id not in self.clients:
            base_url = self.cluster.get_node_address(node_id)
            self.clients[node_id] = RemoteStorageClient(base_url)
        return self.clients[node_id]

    async def write(self, collection: str, doc_id: str, data: dict, w: int = 2) -> Dict[str, Any]:
        replicas = self.cluster.get_replicas(doc_id)
        if len(replicas) < w:
            raise Exception(f"Not enough replicas: required {w}, available {len(replicas)}")

        # 准备新文档
        # 先尝试从主副本获取当前版本（这里简化，直接新建）
        # 实际应该读一下以合并版本，但为简单，我们直接创建新文档
        new_doc = Document(id=doc_id, collection=collection, data=data,
                           version_vector={self.local_node_id: 1})

        # 并发写入所有副本
        tasks = []
        for node in replicas:
            if node == self.local_node_id:
                tasks.append(self.storage.put(collection, doc_id, new_doc))
            else:
                client = self._get_client(node)
                tasks.append(client.put(collection, doc_id, new_doc) if client else asyncio.sleep(0, result=False))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = 0
        for r in results:
            if r is True:
                success_count += 1
            elif isinstance(r, Exception):
                # 记录日志
                pass
        if success_count >= w:
            return {"status": "success", "document": new_doc.to_dict(), "w": success_count}
        else:
            raise Exception(f"Write failed: only {success_count} acks, required {w}")

    async def read(self, collection: str, doc_id: str, r: int = 2) -> Dict[str, Any]:
        replicas = self.cluster.get_replicas(doc_id)
        tasks = []
        for node in replicas:
            if node == self.local_node_id:
                tasks.append(self.storage.get(collection, doc_id))
            else:
                client = self._get_client(node)
                tasks.append(client.get(collection, doc_id) if client else asyncio.sleep(0, result=None))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid_docs = []
        for res in results:
            if isinstance(res, Document):
                valid_docs.append(res)
            elif isinstance(res, Exception):
                # 忽略异常
                pass
        if len(valid_docs) < r:
            raise Exception(f"Read failed: only {len(valid_docs)} responses, required {r}")

        merged = merge_versions(valid_docs)
        return {"status": "success", "document": merged.to_dict(), "replicas_read": len(valid_docs)}

    async def close(self):
        """关闭所有 HTTP 客户端"""
        for client in self.clients.values():
            await client.close()