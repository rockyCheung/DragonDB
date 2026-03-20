from typing import Dict, Optional, List
from models.document import Document

def increment_version(vv: Dict[str, int], node_id: str) -> Dict[str, int]:
    """为指定节点递增版本号"""
    new_vv = vv.copy()
    new_vv[node_id] = new_vv.get(node_id, 0) + 1
    return new_vv

def compare_versions(v1: Dict[str, int], v2: Dict[str, int]) -> Optional[str]:
    """
    比较两个版本向量：
    返回 'before', 'after', 'conflict', 'equal'
    """
    all_keys = set(v1.keys()) | set(v2.keys())
    v1_le_v2 = True
    v2_le_v1 = True
    v1_eq_v2 = True

    for key in all_keys:
        val1 = v1.get(key, 0)
        val2 = v2.get(key, 0)
        if val1 < val2:
            v1_le_v2 = v1_le_v2 and True
            v2_le_v1 = False
            v1_eq_v2 = False
        elif val1 > val2:
            v2_le_v1 = v2_le_v1 and True
            v1_le_v2 = False
            v1_eq_v2 = False
        # 相等时保持标志位不变

    if v1_eq_v2:
        return 'equal'
    if v1_le_v2 and not v2_le_v1:
        return 'before'
    if v2_le_v1 and not v1_le_v2:
        return 'after'
    return 'conflict'

def merge_versions(docs: List[Document], resolver: str = 'LWW') -> Document:
    """
    合并多个版本（简单LWW：取最新时间戳）
    """
    if not docs:
        raise ValueError("No documents to merge")
    if len(docs) == 1:
        return docs[0]
    # 按时间戳降序排序
    docs.sort(key=lambda d: d.timestamp, reverse=True)
    return docs[0]