import asyncio
from typing import Optional, Set
from backend.config import settings

class PortAllocator:
    """Manages port allocation for agent subprocesses"""

    def __init__(self):
        self.start_port = settings.agent_port_range_start
        self.end_port = settings.agent_port_range_end
        self.allocated_ports: Set[int] = set()
        self._lock = asyncio.Lock()

    async def allocate(self) -> Optional[int]:
        """Allocate next available port"""
        async with self._lock:
            for port in range(self.start_port, self.end_port + 1):
                if port not in self.allocated_ports:
                    self.allocated_ports.add(port)
                    return port
            return None

    async def release(self, port: int) -> None:
        """Release a port back to the pool"""
        async with self._lock:
            self.allocated_ports.discard(port)

    def is_allocated(self, port: int) -> bool:
        """Check if port is allocated"""
        return port in self.allocated_ports

port_allocator = PortAllocator()
