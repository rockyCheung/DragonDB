# storage/dragonstore/engine_store.py
import os
import asyncio
from typing import Optional, List, Tuple
from .memtable import SkipList
from .wal import WAL
from .cache import LRUCache
from .compaction import CompactionManager, LeveledCompactionPolicy
from models.document import Document
from .sstable.reader import SSTableReader
from .compaction import SSTableIterator

# 墓碑标记，用于表示键已被删除
TOMBSTONE = b'__tombstone__'

class DragonStore:
    def __init__(self, db_path: str, options: dict = None):
        self.db_path = db_path
        os.makedirs(db_path, exist_ok=True)
        self.options = options or {}
        self.memtable = SkipList()
        self.immutable_memtable = None
        self.wal = WAL(os.path.join(db_path, 'wal.log'), sync=self.options.get('sync_wal', False))
        self.cache = LRUCache(self.options.get('cache_size', 64 * 1024 * 1024))  # 64MB
        self.compaction_manager = CompactionManager(db_path, LeveledCompactionPolicy())
        self.lock = asyncio.Lock()
        self.closed = False

    async def open(self):
        await self.wal.open()
        # 回放 WAL 重建 memtable
        ops = await self.wal.replay()
        for op, key, value in ops:
            if op == 'put':
                self.memtable.put(key, value)
            else:  # delete
                self.memtable.delete(key)
        # 启动后台合并任务
        asyncio.create_task(self._background_compaction())

    async def put(self, key: bytes, value: bytes):
        if self.closed:
            raise Exception("Store closed")
        async with self.lock:
            if self.closed:
                raise Exception("Store closed")
            await self.wal.append([('put', key, value)])
            self.memtable.put(key, value)
            if len(self.memtable) > self.options.get('memtable_size', 4 * 1024 * 1024):
                await self._flush_memtable()

    async def delete(self, key: bytes):
        if self.closed:
            raise Exception("Store closed")
        """删除键，WAL 记录删除操作，MemTable 标记删除"""
        async with self.lock:
            if self.closed:
                raise Exception("Store closed")
            await self.wal.append([('delete', key, None)])
            self.memtable.delete(key)
            if len(self.memtable) > self.options.get('memtable_size', 4 * 1024 * 1024):
                await self._flush_memtable()

    async def get(self, key: bytes) -> Optional[bytes]:
        if self.closed:
            return None
        # 先查内存表
        val = self.memtable.get(key)
        if val is not None:
            return val
        # 查不可变内存表
        if self.immutable_memtable:
            val = self.immutable_memtable.get(key)
            if val is not None:
                return val
        # 查缓存
        cache_key = b'cache:' + key
        cached = self.cache.get(cache_key)
        if cached is not None:
            # 如果缓存值是墓碑，返回 None
            return None if cached == TOMBSTONE else cached
        # 查 SSTable（需要实现层级查找）
        val = await self._search_sstables(key)
        if val is not None:
            self.cache.put(cache_key, val)
        else:
            self.cache.put(cache_key, TOMBSTONE)  # 缓存不存在的标记
        return val

    async def write_batch(self, batch: List[Tuple[str, bytes, Optional[bytes]]]):
        if self.closed:
            raise Exception("Store closed")
        async with self.lock:
            if self.closed:
                raise Exception("Store closed")
            await self.wal.append(batch)
            for op, key, value in batch:
                if op == 'put':
                    self.memtable.put(key, value)
                else:  # delete
                    self.memtable.delete(key)
            if len(self.memtable) > self.options.get('memtable_size', 4 * 1024 * 1024):
                await self._flush_memtable()

    async def _flush_memtable(self):
        """将当前 memtable 转为 immutable 并触发落盘"""
        if self.immutable_memtable:
            # 等待之前的 immutable 落盘完成
            return
        self.immutable_memtable = self.memtable
        self.memtable = SkipList()
        # 启动后台落盘任务
        asyncio.create_task(self._write_immutable_to_sstable())

    async def _write_immutable_to_sstable(self):
        # 将 immutable_memtable 写入 SSTable
        mem = self.immutable_memtable
        if not mem:
            return
        from .sstable.writer import SSTableWriter
        timestamp = int(asyncio.get_event_loop().time())
        filename = f"L0_{timestamp}.sst"
        filepath = os.path.join(self.db_path, filename)
        writer = SSTableWriter(filepath)
        for key, value in mem.items():
            # 如果值是 None（标记删除），写入墓碑值
            writer.add(key, value if value is not None else TOMBSTONE)
        writer.finish()
        # 更新元数据
        self.immutable_memtable = None
        # 通知合并管理器
        await self.compaction_manager.maybe_compact()

    async def _search_sstables(self, key: bytes) -> Optional[bytes]:
        # 从 level 0 开始遍历所有 SSTable，实际应按层级顺序查找
        files = [f for f in os.listdir(self.db_path) if f.endswith('.sst')]
        # 按文件名排序，假设 L0 优先
        files.sort()
        for f in files:
            reader = SSTableReader(os.path.join(self.db_path, f))
            val = reader.get(key)
            reader.close()
            if val is not None:
                # 如果读到的是墓碑，返回 None
                return None if val == TOMBSTONE else val
        return None

    async def _background_compaction(self):
        while not self.closed:
            await asyncio.sleep(10)  # 定期检查
            await self.compaction_manager.maybe_compact()

    async def close(self):
        self.closed = True
        if self.memtable:
            await self._flush_memtable()  # 最后一次落盘
        await self.wal.close()

    # 在 DragonStore 类中添加
    async def get_all_keys(self) -> List[bytes]:
        keys = set()
        # 1. 从当前 memtable 获取
        for key, _ in self.memtable.items():
            keys.add(key)
        # 2. 从 immutable memtable 获取
        if self.immutable_memtable:
            for key, _ in self.immutable_memtable.items():
                keys.add(key)
        # 3. 从所有 SSTable 获取
        files = [f for f in os.listdir(self.db_path) if f.endswith('.sst')]
        for f in files:
            filepath = os.path.join(self.db_path, f)
            reader = None
            try:
                reader = SSTableReader(filepath)
                it = SSTableIterator(reader)
                for key, _ in it:
                    keys.add(key)
            except Exception as e:
                print(f"Warning: Failed to read SSTable {f}: {e}")
            finally:
                if reader:
                    try:
                        reader.close()
                    except:
                        pass
        return list(keys)

    # 在 DragonStore 类中添加
    async def get_all_collections(self) -> List[str]:
        """获取所有集合名称"""
        keys = await self.get_all_keys()
        collections = set()
        for key in keys:
            # 键格式为 "collection:doc_id"
            parts = key.decode().split(':', 1)
            if len(parts) == 2:
                collections.add(parts[0])
        return sorted(collections)

    async def get_documents_by_collection(self, collection: str, limit: int = 100, offset: int = 0) -> List[Document]:
        """获取指定集合的文档列表（支持分页）"""
        keys = await self.get_all_keys()
        # 过滤出该集合的键
        coll_keys = [k for k in keys if k.decode().startswith(f"{collection}:")]
        # 按偏移和限制切片
        page_keys = coll_keys[offset:offset + limit]
        documents = []
        for key in page_keys:
            value = await self.get(key)
            if value is not None:
                # 反序列化为 Document（需要与协调器一致）
                from models.document import Document
                import pickle
                doc = Document.from_dict(pickle.loads(value))
                documents.append(doc)
        return documents