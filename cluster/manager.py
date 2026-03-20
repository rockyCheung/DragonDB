# cluster/manager.py
import bisect
from typing import List, Dict, Optional
from .hashring import ConsistentHashRing

class ClusterManager:
    def __init__(self, local_node_id: str, all_nodes_info: Dict[str, dict],
                 replication_factor: int = 3):
        self.local_node_id = local_node_id
        self.replication_factor = replication_factor
        self.all_nodes_info = all_nodes_info  # {node_id: {'host':..., 'port':...}}
        self.node_ids = list(all_nodes_info.keys())
        self.ring = ConsistentHashRing(self.node_ids, vnodes_per_node=100)

    def get_node_address(self, node_id: str) -> str:
        info = self.all_nodes_info.get(node_id)
        if not info:
            raise ValueError(f"Unknown node {node_id}")
        return f"http://{info['host']}:{info['port']}"

    def get_replicas(self, key: str) -> List[str]:
        if not self.node_ids:
            return []
        hash_val = self.ring._hash(key)
        idx = bisect.bisect_right(self.ring.sorted_keys, hash_val) % len(self.ring.sorted_keys)
        replicas = []
        seen = set()
        for i in range(len(self.ring.sorted_keys)):
            node = self.ring.ring[self.ring.sorted_keys[(idx + i) % len(self.ring.sorted_keys)]]
            if node not in seen:
                replicas.append(node)
                seen.add(node)
            if len(replicas) >= self.replication_factor:
                break
        return replicas

    def add_node(self, node_id: str, node_info: dict):
        """添加新节点到集群（需外部提供节点信息）"""
        if node_id in self.all_nodes_info:
            raise ValueError(f"Node {node_id} already exists")
        self.all_nodes_info[node_id] = node_info
        self.node_ids = list(self.all_nodes_info.keys())
        self.ring.add_node(node_id)
        # 注意：此处不触发数据迁移，需上层调用 migrate_data

    def remove_node(self, node_id: str):
        """从集群移除节点（需确保节点已离线且数据已迁移）"""
        if node_id not in self.all_nodes_info:
            raise ValueError(f"Node {node_id} does not exist")
        if node_id == self.local_node_id:
            raise ValueError("Cannot remove local node")
        del self.all_nodes_info[node_id]
        self.node_ids = list(self.all_nodes_info.keys())
        self.ring.remove_node(node_id)
        # 注意：此处不触发数据迁移，需上层调用 migrate_data