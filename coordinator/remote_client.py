# coordinator/remote_client.py
import aiohttp
import asyncio
import json
from typing import Optional, List
from models.document import Document

class RemoteStorageClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None

    async def _ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def get(self, collection: str, doc_id: str) -> Optional[Document]:
        await self._ensure_session()
        url = f"{self.base_url}/internal/db/{collection}/{doc_id}"
        try:
            async with self.session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return Document.from_dict(data)
                elif resp.status == 404:
                    return None
                else:
                    return None
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return None

    async def put(self, collection: str, doc_id: str, document: Document) -> bool:
        await self._ensure_session()
        url = f"{self.base_url}/internal/db/{collection}/{doc_id}"
        try:
            async with self.session.put(url, json=document.to_dict(), timeout=5) as resp:
                return resp.status == 200
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return False

    async def delete(self, collection: str, doc_id: str) -> bool:
        await self._ensure_session()
        url = f"{self.base_url}/internal/db/{collection}/{doc_id}"
        try:
            async with self.session.delete(url, timeout=5) as resp:
                return resp.status == 200
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return False

    async def close(self):
        if self.session:
            await self.session.close()

    # 在 RemoteStorageClient 类中添加以下方法

    async def get_all_keys(self) -> List[bytes]:
        """从远程节点获取所有键列表"""
        await self._ensure_session()
        url = f"{self.base_url}/internal/raw/keys"
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # 假设返回的是十六进制键列表
                    return [bytes.fromhex(k) for k in data]
                else:
                    return []
        except:
            return []

    async def get_raw(self, key: bytes) -> Optional[bytes]:
        await self._ensure_session()
        url = f"{self.base_url}/internal/raw/{key.hex()}"
        try:
            async with self.session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    return None
        except:
            return None

    async def put_raw(self, key: bytes, value: bytes) -> bool:
        await self._ensure_session()
        url = f"{self.base_url}/internal/raw/{key.hex()}"
        try:
            async with self.session.put(url, data=value, timeout=5) as resp:
                return resp.status == 200
        except:
            return False

    async def send_cluster_update(self, action: str, node_id: str, node_info: dict = None):
        """通知目标节点更新集群视图"""
        await self._ensure_session()
        url = f"{self.base_url}/internal/cluster/update"
        payload = {'action': action, 'node_id': node_id}
        if node_info:
            payload['node_info'] = node_info
        async with self.session.post(url, json=payload) as resp:
            return resp.status == 200