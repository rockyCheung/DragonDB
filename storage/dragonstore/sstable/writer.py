# storage/dragonstore/sstable/writer.py
import os
import struct
from .bloom import BloomFilter

class SSTableWriter:
    def __init__(self, path: str, block_size: int = 4096):
        self.path = path
        self.block_size = block_size
        self.f = open(path, 'wb')
        self.current_block = bytearray()
        self.last_key = None
        self.index_entries = []  # [(last_key, offset)]
        # 预计容量和假阳性率可根据数据量调整
        self.bloom = BloomFilter(10000, 0.01)

    def add(self, key: bytes, value: bytes):
        self.bloom.add(key)
        key_len = len(key)
        val_len = len(value)
        entry = struct.pack('>I', key_len) + key + struct.pack('>I', val_len) + value
        if len(self.current_block) + len(entry) > self.block_size and self.current_block:
            # 当前块已满，写入文件
            offset = self.f.tell()
            self.f.write(self.current_block)
            self.index_entries.append((self.last_key, offset))
            self.current_block = bytearray()
        self.current_block.extend(entry)
        self.last_key = key

    def finish(self):
        # 写入最后一个块
        if self.current_block:
            offset = self.f.tell()
            self.f.write(self.current_block)
            self.index_entries.append((self.last_key, offset))
        # 写入索引块
        index_data = bytearray()
        for last_key, offset in self.index_entries:
            key_len = len(last_key)
            index_data.extend(struct.pack('>I', key_len))
            index_data.extend(last_key)
            index_data.extend(struct.pack('>Q', offset))
        index_offset = self.f.tell()
        self.f.write(index_data)
        # 写入 Bloom Filter
        bloom_data = self.bloom.to_bytes()
        bloom_offset = self.f.tell()
        self.f.write(bloom_data)
        # 写入 Footer
        footer = struct.pack('>QQ', index_offset, bloom_offset)
        self.f.write(footer)
        self.f.close()