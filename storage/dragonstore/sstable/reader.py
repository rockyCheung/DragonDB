# storage/dragonstore/sstable/reader.py
import os
import struct
from typing import Optional, List, Tuple
import bisect
from .bloom import BloomFilter

class SSTableReader:
    def __init__(self, path: str):
        self.path = path
        self.f = open(path, 'rb')
        self.f.seek(0, os.SEEK_END)
        self.file_size = self.f.tell()
        # 读取 footer (最后16字节：index_offset + bloom_offset)
        self.f.seek(self.file_size - 16)
        self.index_offset, self.bloom_offset = struct.unpack('>QQ', self.f.read(16))

        # 读取索引块
        self.f.seek(self.index_offset)
        self.index = self._read_index(self.bloom_offset)

        # 读取 Bloom Filter
        self.f.seek(self.bloom_offset)
        bloom_len = self.file_size - self.bloom_offset - 16
        self.bloom = BloomFilter.from_bytes(self.f.read(bloom_len))

    def _read_index(self, end_offset: int) -> List[Tuple[bytes, int]]:
        index = []
        while self.f.tell() < end_offset:
            key_len_bytes = self.f.read(4)
            if not key_len_bytes or len(key_len_bytes) < 4:
                break
            key_len = struct.unpack('>I', key_len_bytes)[0]
            key = self.f.read(key_len)
            if len(key) < key_len:
                break
            offset_bytes = self.f.read(8)
            if len(offset_bytes) < 8:
                break
            offset = struct.unpack('>Q', offset_bytes)[0]
            index.append((key, offset))
        return index

    def get(self, key: bytes) -> Optional[bytes]:
        if not self.bloom.might_contain(key):
            return None
        keys = [last_key for last_key, _ in self.index]
        idx = bisect.bisect_left(keys, key)
        if idx >= len(keys):
            return None
        last_key, block_offset = self.index[idx]
        # 确定数据块结束位置
        if idx + 1 < len(self.index):
            block_end = self.index[idx + 1][1]
        else:
            block_end = self.bloom_offset
        # 读取数据块
        self.f.seek(block_offset)
        block_data = self.f.read(block_end - block_offset)
        pos = 0
        while pos < len(block_data):
            key_len = struct.unpack('>I', block_data[pos:pos+4])[0]
            pos += 4
            cur_key = block_data[pos:pos+key_len]
            pos += key_len
            val_len = struct.unpack('>I', block_data[pos:pos+4])[0]
            pos += 4
            value = block_data[pos:pos+val_len]
            pos += val_len
            if cur_key == key:
                return value
        return None

    def read_block(self, idx: int) -> bytes:
        """返回第 idx 个数据块的原始字节"""
        if idx < 0 or idx >= len(self.index):
            raise IndexError("block index out of range")
        _, offset = self.index[idx]
        if idx + 1 < len(self.index):
            end = self.index[idx + 1][1]
        else:
            end = self.bloom_offset
        self.f.seek(offset)
        return self.f.read(end - offset)

    def close(self):
        self.f.close()