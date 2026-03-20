# storage/dragonstore/compaction.py
import os
import asyncio
import heapq
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
from .sstable.reader import SSTableReader
from .sstable.writer import SSTableWriter

# ==================== 合并策略 ====================

class CompactionPolicy(ABC):
    @abstractmethod
    def should_compact(self, levels: Dict[int, List[str]]) -> bool:
        pass

    @abstractmethod
    def pick_inputs(self, levels: Dict[int, List[str]]) -> List[str]:
        pass

class LeveledCompactionPolicy(CompactionPolicy):
    def __init__(self,
                 l0_file_num_threshold: int = 4,
                 level_size_multiplier: int = 10,
                 base_level_size_mb: int = 10):
        self.l0_file_num_threshold = l0_file_num_threshold
        self.level_size_multiplier = level_size_multiplier
        self.base_level_size_mb = base_level_size_mb

    def should_compact(self, levels: Dict[int, List[str]]) -> bool:
        if len(levels.get(0, [])) >= self.l0_file_num_threshold:
            return True
        for level, files in levels.items():
            if level == 0:
                continue
            total_size = self._calculate_level_size(files)
            max_size = self.base_level_size_mb * (self.level_size_multiplier ** (level - 1))
            if total_size > max_size:
                return True
        return False

    def pick_inputs(self, levels: Dict[int, List[str]]) -> List[str]:
        if len(levels.get(0, [])) >= self.l0_file_num_threshold:
            return levels[0]
        for level in sorted(levels.keys()):
            if level == 0:
                continue
            files = levels[level]
            total_size = self._calculate_level_size(files)
            max_size = self.base_level_size_mb * (self.level_size_multiplier ** (level - 1))
            if total_size > max_size:
                chosen = files[0]
                next_level_files = levels.get(level + 1, [])
                overlapping = self._find_overlapping_files(chosen, next_level_files)
                return [chosen] + overlapping
        return []

    def _calculate_level_size(self, files: List[str]) -> int:
        total = 0
        for f in files:
            try:
                total += os.path.getsize(f) // (1024 * 1024)
            except OSError:
                pass
        return total

    def _find_overlapping_files(self, target_file: str, candidates: List[str]) -> List[str]:
        # 简化：假设所有候选文件都重叠
        return candidates


# ==================== 迭代器 ====================

class SSTableIterator:
    """顺序遍历单个 SSTable 的所有键值对"""
    def __init__(self, reader: SSTableReader):
        self.reader = reader
        self.current_block_idx = 0
        self.current_block_data = None
        self.block_pos = 0
        self._load_next_block()

    def _load_next_block(self):
        if self.current_block_idx >= len(self.reader.index):
            self.current_block_data = None
            return
        self.current_block_data = self.reader.read_block(self.current_block_idx)
        self.block_pos = 0
        self.current_block_idx += 1

    def __iter__(self):
        return self

    def __next__(self) -> Tuple[bytes, bytes]:
        while True:
            if self.current_block_data is None:
                raise StopIteration

            # 检查 key_len 是否完整
            if self.block_pos + 4 > len(self.current_block_data):
                self._load_next_block()
                continue

            key_len = int.from_bytes(
                self.current_block_data[self.block_pos:self.block_pos+4], 'big'
            )
            # 跳过零长度键（填充字节）
            if key_len == 0:
                self.block_pos += 4
                continue

            # 检查 key 是否完整
            if self.block_pos + 4 + key_len > len(self.current_block_data):
                self._load_next_block()
                continue

            self.block_pos += 4
            key = self.current_block_data[self.block_pos:self.block_pos+key_len]
            self.block_pos += key_len

            # 检查 val_len 是否完整
            if self.block_pos + 4 > len(self.current_block_data):
                self._load_next_block()
                continue

            val_len = int.from_bytes(
                self.current_block_data[self.block_pos:self.block_pos+4], 'big'
            )
            # 检查 value 是否完整
            if self.block_pos + 4 + val_len > len(self.current_block_data):
                self._load_next_block()
                continue

            self.block_pos += 4
            value = self.current_block_data[self.block_pos:self.block_pos+val_len]
            self.block_pos += val_len

            # 跳过零长度值（可能是无效条目）
            if val_len == 0:
                continue

            return key, value

class MergingIterator:
    """多路归并迭代器：合并多个有序迭代器，按 key 顺序输出"""
    def __init__(self, iterators: List[SSTableIterator]):
        self.heap = []
        for i, it in enumerate(iterators):
            try:
                first_key, first_val = next(it)
                heapq.heappush(self.heap, (first_key, first_val, i, it))
            except StopIteration:
                pass

    def __iter__(self):
        return self

    def __next__(self) -> Tuple[bytes, bytes]:
        if not self.heap:
            raise StopIteration
        key, value, idx, it = heapq.heappop(self.heap)
        try:
            next_key, next_val = next(it)
            heapq.heappush(self.heap, (next_key, next_val, idx, it))
        except StopIteration:
            pass
        return key, value


# ==================== 合并管理器 ====================

class CompactionManager:
    def __init__(self, db_path: str, policy: CompactionPolicy = None):
        self.db_path = db_path
        self.policy = policy or LeveledCompactionPolicy()
        self.lock = asyncio.Lock()
        self.running = False

    async def maybe_compact(self):
        async with self.lock:
            if self.running:
                return
            levels = self._load_levels()
            if self.policy.should_compact(levels):
                self.running = True
                asyncio.create_task(self._compact(levels))

    async def _compact(self, levels: Dict[int, List[str]]):
        try:
            inputs = self.policy.pick_inputs(levels)
            if not inputs:
                return
            new_files = await self._merge_files(inputs)
            self._update_metadata(new_files, inputs)
        finally:
            self.running = False

    async def _merge_files(self, input_files: List[str]) -> List[str]:
        if not input_files:
            return []
        readers = [SSTableReader(f) for f in input_files]
        iterators = [SSTableIterator(r) for r in readers]
        merging_iter = MergingIterator(iterators)
        timestamp = int(asyncio.get_event_loop().time())
        new_file = os.path.join(self.db_path, f"L1_{timestamp}.sst")
        writer = SSTableWriter(new_file)
        for key, value in merging_iter:
            writer.add(key, value)
        writer.finish()
        for r in readers:
            r.close()
        return [new_file]

    def _load_levels(self) -> Dict[int, List[str]]:
        levels = {}
        pattern = re.compile(r'L(\d+)_\d+\.sst$')
        for fname in os.listdir(self.db_path):
            if not fname.endswith('.sst'):
                continue
            match = pattern.match(fname)
            if match:
                level = int(match.group(1))
                full_path = os.path.join(self.db_path, fname)
                levels.setdefault(level, []).append(full_path)
        for level in levels:
            levels[level].sort()
        return levels

    def _update_metadata(self, new_files: List[str], old_files: List[str]):
        for f in old_files:
            try:
                os.remove(f)
            except OSError:
                pass