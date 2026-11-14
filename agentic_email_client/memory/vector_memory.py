"""
Vector-based memory system for storing and retrieving conversation context.

Four distinct memory types:
- Customer Memory: Customer preferences, contacts, history
- Thread Memory: Conversation context and commitments
- Company Memory: Products, policies, prices, procedures
- Agent Memory: Role, instructions, decisions, performance
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import asyncio
import json
import hashlib


class MemoryType(Enum):
    CUSTOMER = "customer"
    THREAD = "thread"
    COMPANY = "company"
    AGENT = "agent"


class VectorMemory:
    """Multi-type memory system for conversation context."""

    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id
        self._stores: Dict[MemoryType, Dict[str, Dict[str, Any]]] = {
            MemoryType.CUSTOMER: {},
            MemoryType.THREAD: {},
            MemoryType.COMPANY: {},
            MemoryType.AGENT: {},
        }

    def _get_key(self, memory_type: MemoryType, identifier: str) -> str:
        """Generate unique key for memory entry."""
        if self.tenant_id:
            return hashlib.sha256(f"{self.tenant_id}:{memory_type.value}:{identifier}".encode()).hexdigest()
        return hashlib.sha256(f"{memory_type.value}:{identifier}".encode()).hexdigest()

    # Customer Memory Methods
    async def store_customer(self, customer_id: str, data: Dict[str, Any]) -> str:
        """Store customer profile and history."""
        key = self._get_key(MemoryType.CUSTOMER, customer_id)
        self._stores[MemoryType.CUSTOMER][key] = {
            "customer_id": customer_id,
            "data": data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return key

    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve customer profile."""
        key = self._get_key(MemoryType.CUSTOMER, customer_id)
        entry = self._stores[MemoryType.CUSTOMER].get(key)
        return entry["data"] if entry else None

    async def search_customers(self, query: str) -> List[Dict[str, Any]]:
        """Search customers by query (name, email, company)."""
        results = []
        query_lower = query.lower()
        for entry in self._stores[MemoryType.CUSTOMER].values():
            data = entry.get("data", {})
            if any(query_lower in str(v).lower() for v in data.values()):
                results.append(entry)
        return results

    def list_customers(self) -> List[Dict[str, Any]]:
        """List all customers."""
        return list(self._stores[MemoryType.CUSTOMER].values())

    # Thread Memory Methods
    async def store_thread(self, thread_id: str, data: Dict[str, Any]) -> str:
        """Store conversation thread context."""
        key = self._get_key(MemoryType.THREAD, thread_id)
        self._stores[MemoryType.THREAD][key] = {
            "thread_id": thread_id,
            "data": data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return key

    async def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve thread context."""
        key = self._get_key(MemoryType.THREAD, thread_id)
        entry = self._stores[MemoryType.THREAD].get(key)
        return entry["data"] if entry else None

    async def update_thread(self, thread_id: str, updates: Dict[str, Any]) -> bool:
        """Update thread context with new information."""
        key = self._get_key(MemoryType.THREAD, thread_id)
        if key in self._stores[MemoryType.THREAD]:
            entry = self._stores[MemoryType.THREAD][key]
            if "context" in entry["data"]:
                entry["data"]["context"].update(updates)
            else:
                entry["data"]["context"] = updates
            entry["updated_at"] = datetime.now().isoformat()
            return True
        return False

    def list_threads(self) -> List[Dict[str, Any]]:
        """List all threads."""
        return list(self._stores[MemoryType.THREAD].values())

    # Company Memory Methods
    async def store_company(self, key: str, data: Dict[str, Any]) -> str:
        """Store company knowledge (products, policies, prices)."""
        entry_id = hashlib.md5(key.encode()).hexdigest()
        self._stores[MemoryType.COMPANY][entry_id] = {
            "key": key,
            "data": data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return entry_id

    async def get_company(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve company knowledge by key."""
        entry_id = hashlib.md5(key.encode()).hexdigest()
        entry = self._stores[MemoryType.COMPANY].get(entry_id)
        return entry["data"] if entry else None

    async def search_company(self, query: str) -> List[Dict[str, Any]]:
        """Search company knowledge."""
        results = []
        query_lower = query.lower()
        for entry in self._stores[MemoryType.COMPANY].values():
            data = entry.get("data", {})
            if any(query_lower in str(v).lower() for v in data.values()):
                results.append(entry)
        return results

    def list_company(self) -> List[Dict[str, Any]]:
        """List all company knowledge."""
        return list(self._stores[MemoryType.COMPANY].values())

    # Agent Memory Methods
    async def store_agent_memory(self, agent_id: str, key: str, data: Dict[str, Any]) -> str:
        """Store agent memory (performance, decisions, metrics)."""
        entry_id = hashlib.md5(f"{agent_id}:{key}".encode()).hexdigest()
        self._stores[MemoryType.AGENT][entry_id] = {
            "agent_id": agent_id,
            "key": key,
            "data": data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return entry_id

    async def get_agent_memory(self, agent_id: str, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve agent memory."""
        entry_id = hashlib.md5(f"{agent_id}:{key}".encode()).hexdigest()
        entry = self._stores[MemoryType.AGENT].get(entry_id)
        return entry["data"] if entry else None

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agent memories."""
        return list(self._stores[MemoryType.AGENT].values())

    # Legacy methods for backward compatibility
    async def store(self, query: str, metadata: Dict[str, Any] = None, embedding: str = "") -> str:
        """Store a generic memory entry (backward compatible)."""
        key = self._get_key(MemoryType.THREAD, query)
        self._stores[MemoryType.THREAD][key] = {
            "query": query,
            "metadata": metadata,
            "embedding": embedding,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return key

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search all memories (backward compatible)."""
        results = []
        for mem_type in MemoryType:
            if mem_type == MemoryType.CUSTOMER:
                results.extend(await self.search_customers(query))
            elif mem_type == MemoryType.THREAD:
                results.extend(await self._search_thread_memories(query))
        return results[:limit]

    async def _search_thread_memories(self, query: str) -> List[Dict[str, Any]]:
        """Helper to search thread memories."""
        results = []
        query_lower = query.lower()
        for entry in self._stores[MemoryType.THREAD].values():
            # Legacy format: {query: str, metadata: dict, ...}
            entry_query = entry.get("query", "")
            if entry_query and query_lower in entry_query.lower():
                results.append(entry)
            # New format: {thread_id: str, data: dict, ...}
            else:
                data = entry.get("data", {})
                if any(query_lower in str(v).lower() for v in data.values()):
                    results.append(entry)
        return results

    async def get(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Get from thread memory (backward compatible)."""
        # Try exact key match first
        entries = self._stores[MemoryType.THREAD]
        if entry_id in entries:
            return entries[entry_id]
        # Try to find by key generation
        key = self._get_key(MemoryType.THREAD, entry_id)
        if key in entries:
            return entries[key]
        # Search for entry with matching query (legacy format)
        for entry in entries.values():
            if entry.get('query') == entry_id:
                return entry
        return None

    async def delete(self, memory_type: MemoryType, identifier: str) -> bool:
        """Delete a memory entry by type and identifier."""
        key = self._get_key(memory_type, identifier)
        if key in self._stores[memory_type]:
            del self._stores[memory_type][key]
            return True
        return False

    def clear(self, memory_type: MemoryType = None) -> None:
        """Clear all memories or specific type."""
        if memory_type:
            self._stores[memory_type].clear()
        else:
            for store in self._stores.values():
                store.clear()

    def __len__(self) -> int:
        """Return total count of all stored entries."""
        return sum(len(store) for store in self._stores.values())

    def count(self, memory_type: MemoryType = None) -> int:
        """Return count of entries, optionally by type."""
        if memory_type:
            return len(self._stores[memory_type])
        return len(self)

    async def list_all(self) -> List[Dict[str, Any]]:
        """List all memory entries with type information."""
        entries = []
        for mem_type, store in self._stores.items():
            for entry in store.values():
                entry["memory_type"] = mem_type.value
                entries.append(entry)
        return entries

    # Export/Import for persistence
    def export(self) -> str:
        """Export all memory as JSON."""
        data = {}
        for mem_type, store in self._stores.items():
            data[mem_type.value] = store
        return json.dumps(data, default=str)

    async def import_data(self, json_data: str) -> None:
        """Import memory from JSON."""
        data = json.loads(json_data)
        for mem_type_str, store in data.items():
            mem_type = MemoryType(mem_type_str)
            self._stores[mem_type] = store