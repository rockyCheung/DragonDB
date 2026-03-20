# storage/dragonstore/memtable.py
import random
from typing import Optional, List, Tuple

class SkipListNode:
    __slots__ = ('key', 'value', 'deleted', 'level', 'forward')
    def __init__(self, key: bytes, value: Optional[bytes], deleted: bool, level: int):
        self.key = key
        self.value = value
        self.deleted = deleted
        self.level = level
        self.forward = [None] * (level + 1)

class SkipList:
    MAX_LEVEL = 16
    P = 0.5

    def __init__(self):
        self.head = SkipListNode(b'', None, False, self.MAX_LEVEL)
        self.level = 0
        self.size = 0

    def random_level(self) -> int:
        lvl = 0
        while random.random() < self.P and lvl < self.MAX_LEVEL:
            lvl += 1
        return lvl

    def put(self, key: bytes, value: bytes):
        update = [None] * (self.MAX_LEVEL + 1)
        x = self.head
        for i in range(self.level, -1, -1):
            while x.forward[i] and x.forward[i].key < key:
                x = x.forward[i]
            update[i] = x
        x = x.forward[0] if x.forward else None
        if x and x.key == key:
            # 更新现有节点
            x.value = value
            x.deleted = False
            return
        # 插入新节点
        new_level = self.random_level()
        if new_level > self.level:
            for i in range(self.level + 1, new_level + 1):
                update[i] = self.head
            self.level = new_level
        new_node = SkipListNode(key, value, False, new_level)
        for i in range(new_level + 1):
            new_node.forward[i] = update[i].forward[i]
            update[i].forward[i] = new_node
        self.size += 1

    def get(self, key: bytes) -> Optional[bytes]:
        x = self.head
        for i in range(self.level, -1, -1):
            while x.forward[i] and x.forward[i].key < key:
                x = x.forward[i]
        x = x.forward[0] if x.forward else None
        if x and x.key == key and not x.deleted:
            return x.value
        return None

    def delete(self, key: bytes):
        update = [None] * (self.MAX_LEVEL + 1)
        x = self.head
        for i in range(self.level, -1, -1):
            while x.forward[i] and x.forward[i].key < key:
                x = x.forward[i]
            update[i] = x
        x = x.forward[0] if x.forward else None
        if x and x.key == key:
            x.deleted = True
            self.size -= 1

    def items(self) -> List[Tuple[bytes, Optional[bytes]]]:
        """返回所有未删除的键值对（用于迭代）"""
        result = []
        x = self.head.forward[0]
        while x:
            if not x.deleted:
                result.append((x.key, x.value))
            x = x.forward[0]
        return result

    def __len__(self):
        return self.size