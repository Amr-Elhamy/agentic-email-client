"""
Vector-based memory system for storing and retrieving conversation context.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import json


class VectorMemory:
    """Simple in-memory vector storage for conversation context."""

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._vectors: Dict[str, List[float]] = {}

    async def store(
        self,
        query: str,
        metadata: Dict[str, Any] = None,
        embedding: str = "",
    ) -> str:
        """Store a memory entry with optional embedding."""
        import hashlib
        entry_id = hashlib.md5(query.encode()).hexdigest()

        self._store[entry_id] = {
            "query": query,
            "metadata": metadata or {},
            "embedding": embedding,
            "created_at": datetime.now().isoformat(),
        }

        return entry_id

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant memories by query."""
        # Simple keyword-based search for prototype
        results = []
        query_lower = query.lower()

        for entry_id, entry in self._store.items():
            # Check if query matches stored query or metadata
            stored_query = entry.get("query", "").lower()
            if query_lower in stored_query:
                results.append(entry)

        # Sort by most recent first
        results.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )

        return results[:limit]

    async def get(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory entry."""
        return self._store.get(entry_id)

    async def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        if entry_id in self._store:
            del self._store[entry_id]
            self._vectors.pop(entry_id, None)
            return True
        return False

    def clear(self) -> None:
        """Clear all stored memories."""
        self._store.clear()
        self._vectors.clear()

    def __len__(self) -> int:
        """Return number of stored entries."""
        return len(self._store)

    async def list_all(self) -> List[Dict[str, Any]]:
        """List all memory entries."""
        entries = []
        for entry_id, entry in self._store.items():
            entry["id"] = entry_id
            entries.append(entry)
        return entries