# storage/dragonstore/sstable/bloom.py
import math
import mmh3
import struct
from array import array
from typing import Optional

class BloomFilter:
    def __init__(self, capacity: int, error_rate: float):
        self.capacity = capacity
        self.error_rate = error_rate
        self.bit_size = self._compute_bit_size(capacity, error_rate)
        self.hash_count = self._compute_hash_count(self.bit_size, capacity)
        self.bits = array('B', [0]) * ((self.bit_size + 7) // 8)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'BloomFilter':
        # 格式：4字节容量，4字节error_rate(float)，4字节hash_count，4字节bit_size，然后是位数组
        offset = 0
        capacity = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        error_rate = struct.unpack('>f', data[offset:offset+4])[0]
        offset += 4
        hash_count = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        bit_size = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        bf = cls(capacity, error_rate)
        bf.hash_count = hash_count
        bf.bit_size = bit_size
        # 读取位数组
        byte_len = (bit_size + 7) // 8
        bf.bits = array('B', data[offset:offset+byte_len])
        return bf

    def to_bytes(self) -> bytes:
        data = bytearray()
        data.extend(struct.pack('>I', self.capacity))
        data.extend(struct.pack('>f', self.error_rate))
        data.extend(struct.pack('>I', self.hash_count))
        data.extend(struct.pack('>I', self.bit_size))
        data.extend(self.bits.tobytes())
        return bytes(data)

    def _compute_bit_size(self, n, p):
        return int(-n * math.log(p) / (math.log(2) ** 2))

    def _compute_hash_count(self, m, n):
        return int((m / n) * math.log(2))

    def _hashes(self, key: bytes):
        # 使用 MurmurHash3 生成多个哈希值，种子转换为无符号整数
        h1 = mmh3.hash(key, 0) & 0xffffffff
        h2 = mmh3.hash(key, h1) & 0xffffffff
        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.bit_size

    def add(self, key: bytes):
        for bit in self._hashes(key):
            byte_idx = bit // 8
            bit_idx = bit % 8
            self.bits[byte_idx] |= (1 << bit_idx)

    def might_contain(self, key: bytes) -> bool:
        for bit in self._hashes(key):
            byte_idx = bit // 8
            bit_idx = bit % 8
            if not (self.bits[byte_idx] & (1 << bit_idx)):
                return False
        return True