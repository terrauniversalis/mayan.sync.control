"""Routing matrix management for Mayan Sync Control."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .models import Host, RoutingAssignment, RoutingMode


class Router:
    """In-memory routing matrix for mapping devices to hosts."""

    def __init__(self) -> None:
        self._hosts: Dict[str, Host] = {}
        self._assignments: Dict[str, List[RoutingAssignment]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Host management
    # ------------------------------------------------------------------
    def register_host(self, host: Host) -> None:
        self._hosts[host.host_id] = host

    def register_hosts(self, hosts: Iterable[Host]) -> None:
        for host in hosts:
            self.register_host(host)

    def get_host(self, host_id: str) -> Optional[Host]:
        return self._hosts.get(host_id)

    # ------------------------------------------------------------------
    # Assignment management
    # ------------------------------------------------------------------
    def assign(self, u_sha: str, host_id: str, mode: RoutingMode) -> RoutingAssignment:
        if host_id not in self._hosts:
            raise KeyError(f"Host '{host_id}' is not registered")
        assignments = self._assignments[u_sha]
        for assignment in assignments:
            if assignment.host_id == host_id:
                assignment.mode = mode
                return assignment
        assignment = RoutingAssignment(u_sha=u_sha, host_id=host_id, mode=mode)
        assignments.append(assignment)
        assignments.sort(key=lambda item: (self._hosts[item.host_id].priority * -1, item.host_id))
        return assignment

    def release(self, u_sha: str, host_id: str) -> None:
        assignments = self._assignments.get(u_sha)
        if not assignments:
            return
        self._assignments[u_sha] = [a for a in assignments if a.host_id != host_id]
        if not self._assignments[u_sha]:
            del self._assignments[u_sha]

    def release_device(self, u_sha: str) -> None:
        self._assignments.pop(u_sha, None)

    def list_assignments(self, u_sha: Optional[str] = None) -> Dict[str, List[RoutingAssignment]]:
        if u_sha:
            return {u_sha: list(self._assignments.get(u_sha, []))}
        return {key: list(value) for key, value in self._assignments.items()}

    def list_hosts(self) -> List[Host]:
        return sorted(self._hosts.values(), key=lambda host: (-host.priority, host.host_id))
