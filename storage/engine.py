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

    async def close(self):
        """关闭存储引擎（内存存储无需操作）"""
        pass