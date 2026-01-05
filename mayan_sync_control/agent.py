"""Runtime agent orchestrating discovery, inventory and routing."""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
from typing import AsyncIterator, Callable, Dict, Iterable, List, Optional

from .inventory import InventoryService
from .models import (
    AgentConfig,
    ConnectionType,
    DeviceDescriptor,
    DeviceRegistration,
    DeviceStatus,
    Host,
    RoutingMode,
)
from .router import Router

_LOGGER = logging.getLogger(__name__)


class DeviceEvent:
    """Represents a device state change coming from a monitor."""

    def __init__(self, descriptor: DeviceDescriptor, connected: bool = True) -> None:
        self.descriptor = descriptor
        self.connected = connected

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        state = "connected" if self.connected else "disconnected"
        return f"DeviceEvent({self.descriptor.vendor}/{self.descriptor.product}, {state})"


class DeviceMonitor:
    """Base class for device monitors feeding events to the agent."""

    async def watch(self) -> AsyncIterator[DeviceEvent]:  # pragma: no cover - interface
        raise NotImplementedError


class LoopbackMonitor(DeviceMonitor):
    """Simple monitor fed from an in-memory queue (primarily for tests/demo)."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[DeviceEvent] = asyncio.Queue()

    async def watch(self) -> AsyncIterator[DeviceEvent]:
        while True:
            event = await self._queue.get()
            yield event

    def push(self, event: DeviceEvent) -> None:
        self._queue.put_nowait(event)


class Agent:
    """Coordinates device discovery, inventory registration and routing."""

    def __init__(
        self,
        inventory: InventoryService,
        router: Router,
        *,
        monitors: Optional[Iterable[DeviceMonitor]] = None,
        config: Optional[AgentConfig] = None,
    ) -> None:
        self.inventory = inventory
        self.router = router
        self.monitors = list(monitors or [])
        self.config = config or AgentConfig()
        self._event_listeners: List[Callable[[DeviceRegistration], None]] = []
        self._default_profiles = self.config.default_profiles
        self.router.register_hosts(self.config.hosts)
        if self.config.inventory_path:
            _LOGGER.info("Persisting inventory data at %s", self.config.inventory_path)

    # ------------------------------------------------------------------
    # Registration and routing
    # ------------------------------------------------------------------
    def register_listener(self, callback: Callable[[DeviceRegistration], None]) -> None:
        self._event_listeners.append(callback)

    def _emit(self, registration: DeviceRegistration) -> None:
        for callback in list(self._event_listeners):
            try:
                callback(registration)
            except Exception as exc:  # pragma: no cover - defensive
                _LOGGER.exception("Listener %r failed: %s", callback, exc)

    def _activate_device(self, descriptor: DeviceDescriptor) -> DeviceRegistration:
        registration = self.inventory.register(descriptor)
        if not registration.profiles:
            default_profiles = self._resolve_default_profiles(registration)
            if default_profiles:
                self.inventory.attach_profiles(registration.u_sha, default_profiles)
        registration.status = DeviceStatus.ACTIVE
        self._emit(registration)
        return registration

    def _deactivate_device(self, descriptor: DeviceDescriptor) -> None:
        u_sha = self.inventory.compute_u_sha(descriptor)
        registration = self.inventory.get(u_sha)
        if registration:
            registration.status = DeviceStatus.DISCONNECTED
            self.inventory.update_status(u_sha, DeviceStatus.DISCONNECTED)
            self.router.release_device(u_sha)
            self._emit(registration)

    def assign_hosts(
        self,
        registration: DeviceRegistration,
        assignments: Dict[str, RoutingMode],
    ) -> None:
        for host_id, mode in assignments.items():
            self.router.assign(registration.u_sha, host_id, mode)
        self.inventory.assign_hosts(registration.u_sha, assignments.keys())

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------
    async def run(self) -> None:
        if not self.monitors:
            _LOGGER.warning("Agent started without monitors")
            return
        tasks = [asyncio.create_task(self._consume(monitor)) for monitor in self.monitors]
        _LOGGER.info("Agent started with %d monitor(s)", len(tasks))
        await asyncio.gather(*tasks)

    async def _consume(self, monitor: DeviceMonitor) -> None:
        async for event in monitor.watch():
            if event.connected:
                registration = self._activate_device(event.descriptor)
                self._apply_default_routing(registration)
            else:
                self._deactivate_device(event.descriptor)

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def _apply_default_routing(self, registration: DeviceRegistration) -> None:
        assignments: Dict[str, RoutingMode] = {}
        for host in self.router.list_hosts():
            preferred = registration.descriptor.metadata.get("preferred_host")
            if preferred and preferred != host.host_id:
                continue
            mode_str = registration.descriptor.metadata.get("routing_mode", RoutingMode.PRIMARY.value)
            try:
                mode = RoutingMode(mode_str)
            except ValueError:
                mode = RoutingMode.PRIMARY
            assignments[host.host_id] = mode
        if assignments:
            self.assign_hosts(registration, assignments)

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------
    def _resolve_default_profiles(self, registration: DeviceRegistration) -> List[str]:
        direct = self._default_profiles.get(registration.u_sha)
        if direct:
            return direct
        key = f"{registration.descriptor.vendor}:{registration.descriptor.product}"
        return self._default_profiles.get(key, [])

    @classmethod
    def from_config(cls, path: pathlib.Path) -> "Agent":
        config = _load_config(path)
        inventory_path = pathlib.Path(config.get("inventory", {}).get("path", path.with_suffix(".inventory.json")))
        inventory = InventoryService(storage_path=inventory_path)
        hosts = [
            Host(host_id=item["id"], label=item.get("label", item["id"]), priority=item.get("priority", 0))
            for item in config.get("hosts", [])
        ]
        default_profiles = {
            key: list(value)
            for key, value in config.get("profiles", {}).items()
            if isinstance(value, list)
        }
        agent_config = AgentConfig(
            hosts=hosts,
            default_profiles=default_profiles,
            inventory_path=str(inventory_path),
        )
        loopback = LoopbackMonitor()
        agent = cls(inventory, Router(), monitors=[loopback], config=agent_config)
        seed_events = config.get("seed_devices", [])
        for seed in seed_events:
            try:
                connection = ConnectionType(seed.get("connection", ConnectionType.USB.value))
            except ValueError:
                connection = ConnectionType.USB
            descriptor = DeviceDescriptor(
                vendor=seed["vendor"],
                product=seed["product"],
                connection=connection,
                identifiers=seed.get("identifiers", {}),
                metadata=seed.get("metadata", {}),
            )
            loopback.push(DeviceEvent(descriptor, connected=seed.get("connected", True)))
        return agent


def _load_config(path: pathlib.Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(path)
    raw = path.read_text()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse config: {exc}") from exc
