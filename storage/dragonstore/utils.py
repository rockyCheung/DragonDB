# storage/dragonstore/utils.py
import struct

def encode_key(collection: str, doc_id: str) -> bytes:
    """将集合名和文档ID编码为存储键"""
    return f"{collection}:{doc_id}".encode()

def decode_key(key: bytes) -> tuple:
    """从存储键解码集合名和文档ID"""
    parts = key.decode().split(':', 1)
    return parts[0], parts[1]

def uint32_to_bytes(n: int) -> bytes:
    return struct.pack('>I', n)

def bytes_to_uint32(b: bytes) -> int:
    return struct.unpack('>I', b)[0]

def uint64_to_bytes(n: int) -> bytes:
    return struct.pack('>Q', n)

def bytes_to_uint64(b: bytes) -> int:
    return struct.unpack('>Q', b)[0]