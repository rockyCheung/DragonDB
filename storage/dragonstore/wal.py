# storage/dragonstore/wal.py
import os
import struct
import aiofiles
import asyncio
from typing import List, Tuple, Optional

class WAL:
    def __init__(self, path: str, sync: bool = False):
        self.path = path
        self.sync = sync
        self.file = None
        self.lock = asyncio.Lock()

    async def open(self):
        self.file = await aiofiles.open(self.path, 'ab')

    async def append(self, operations: List[Tuple[str, bytes, Optional[bytes]]]):
        """operations: (op_type, key, value)  op_type: 'put' or 'delete'"""
        data = bytearray()
        for op in operations:
            op_type, key, value = op
            if op_type == 'put':
                data.append(0)  # PUT
                data.extend(struct.pack('>I', len(key)))
                data.extend(key)
                data.extend(struct.pack('>I', len(value)))
                data.extend(value)
            else:  # delete
                data.append(1)  # DELETE
                data.extend(struct.pack('>I', len(key)))
                data.extend(key)
        async with self.lock:
            await self.file.write(data)
            if self.sync:
                await self.file.flush()
                os.fsync(self.file.fileno())

    async def replay(self) -> List[Tuple[str, bytes, Optional[bytes]]]:
        """回放日志，返回操作列表"""
        ops = []
        if not os.path.exists(self.path):
            return ops
        async with aiofiles.open(self.path, 'rb') as f:
            while True:
                type_byte = await f.read(1)
                if not type_byte:
                    break
                op_type = 'put' if type_byte[0] == 0 else 'delete'
                key_len_bytes = await f.read(4)
                if len(key_len_bytes) < 4:
                    break
                key_len = struct.unpack('>I', key_len_bytes)[0]
                key = await f.read(key_len)
                if len(key) < key_len:
                    break
                if op_type == 'put':
                    val_len_bytes = await f.read(4)
                    if len(val_len_bytes) < 4:
                        break
                    val_len = struct.unpack('>I', val_len_bytes)[0]
                    value = await f.read(val_len)
                    if len(value) < val_len:
                        break
                    ops.append(('put', key, value))
                else:
                    ops.append(('delete', key, None))
        return ops

    async def close(self):
        if self.file:
            await self.file.close()