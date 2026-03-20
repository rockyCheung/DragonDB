# cluster/migration.py
import asyncio
from typing import List
from coordinator.remote_client import RemoteStorageClient
from storage.dragonstore.engine_store import DragonStore
from cluster.manager import ClusterManager

class DataMigration:
    def __init__(self, local_node_id: str, local_store: DragonStore,
                 cluster_manager: ClusterManager):
        self.local_node_id = local_node_id
        self.local_store = local_store
        self.cluster = cluster_manager
        self.clients = {}  # 缓存远程客户端

    def _get_client(self, node_id: str) -> RemoteStorageClient:
        if node_id == self.local_node_id:
            return None
        if node_id not in self.clients:
            url = self.cluster.get_node_address(node_id)
            self.clients[node_id] = RemoteStorageClient(url)
        return self.clients[node_id]

    async def migrate_data_for_new_node(self, new_node_id: str):
        """将本节点上属于新节点的数据推送过去"""
        # 获取所有本地键（简化：使用存储引擎的迭代器）
        all_keys = await self._get_all_keys()
        for key in all_keys:
            # 解码 collection 和 doc_id（假设键格式为 "collection:doc_id"）
            try:
                parts = key.decode().split(':', 1)
                if len(parts) != 2:
                    continue
                collection, doc_id = parts
            except UnicodeDecodeError:
                continue

            # 计算新节点是否应该是该键的副本
            replicas = self.cluster.get_replicas(doc_id)
            if new_node_id in replicas:
                # 读取本地值
                value = await self.local_store.get(key)
                if value is None:
                    continue
                # 推送到新节点
                client = self._get_client(new_node_id)
                if client:
                    success = await client.put_raw(key, value)
                    # 可选：记录日志
        print(f"Data migration to {new_node_id} completed.")

    async def migrate_data_for_removed_node(self, removed_node_id: str):
        """从其他节点拉取原本属于被删除节点的数据（如果本节点是新副本）"""
        # 获取所有本地键（但我们需要的是可能缺失的键）
        # 由于不知道所有键，我们采用反向方式：从其他节点获取它们拥有的属于本节点的数据？
        # 更简单：遍历所有可能键的成本太高，我们改为：
        # 1. 获取所有在线节点列表
        online_nodes = [n for n in self.cluster.node_ids if n != self.local_node_id]
        # 2. 从每个节点请求其所有键（或按范围），但效率低。
        # 这里采用折中：当节点删除后，其他节点可能会在读取时发现缺失，我们依赖读取修复机制。
        # 为了主动迁移，我们只能假设所有需要的数据在删除节点离线后无法访问，必须从其他副本复制。
        # 但不知道哪些键缺失，因此只能被动等待读取请求或触发全量扫描。
        # 这里我们实现一个简化的主动迁移：对于本地存储中的每个键，如果该键在新环下应该由本节点负责，
        # 但本节点没有，则尝试从其他副本拉取。但本节点不知道哪些键缺失，所以需要先知道所有键的列表。
        # 我们可以从所有在线节点获取它们所有的键，合并去重，然后检查本地是否缺少。
        # 这可能导致大量网络传输，但作为管理操作可以接受。
        all_keys_set = set()
        # 从本地获取
        local_keys = await self._get_all_keys()
        all_keys_set.update(local_keys)

        # 从其他节点获取键列表（假设节点提供获取所有键的接口）
        for node in online_nodes:
            client = self._get_client(node)
            if client:
                keys = await client.get_all_keys()
                if keys:
                    all_keys_set.update(keys)

        # 对于每个键，检查在新环下本节点是否是副本，且本地没有
        for key in all_keys_set:
            try:
                parts = key.decode().split(':', 1)
                if len(parts) != 2:
                    continue
                collection, doc_id = parts
            except:
                continue
            replicas = self.cluster.get_replicas(doc_id)
            if self.local_node_id in replicas:
                # 检查本地是否存在
                value = await self.local_store.get(key)
                if value is None:
                    # 从其他在线节点拉取
                    for node in online_nodes:
                        client = self._get_client(node)
                        if client:
                            value = await client.get_raw(key)
                            if value:
                                await self.local_store.put(key, value)
                                break
        print(f"Data migration after removal of {removed_node_id} completed.")

    async def _get_all_keys(self) -> List[bytes]:
        """获取本地存储中的所有键（需要存储引擎支持）"""
        # 假设 DragonStore 实现了 get_all_keys 方法
        # 如果没有，可以添加一个方法，例如遍历 MemTable 和 SSTable
        # 这里调用存储引擎的新方法
        return await self.local_store.get_all_keys()

    async def close(self):
        for client in self.clients.values():
            await client.close()