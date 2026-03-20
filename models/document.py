# dragondb/models/document.py
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class Document:
    id: str
    collection: str
    data: Dict[str, Any]
    version_vector: Dict[str, int] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "collection": self.collection,
            "data": self.data,
            "version_vector": self.version_vector,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Document":
        return cls(
            id=d["id"],
            collection=d["collection"],
            data=d["data"],
            version_vector=d.get("version_vector", {}),
            timestamp=d.get("timestamp", time.time())
        )