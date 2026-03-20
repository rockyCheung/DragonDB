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