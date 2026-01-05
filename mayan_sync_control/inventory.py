"""Inventory service for Mayan Sync Control."""

from __future__ import annotations

import json
import pathlib
import threading
from dataclasses import asdict
from hashlib import sha256
from typing import Dict, Iterable, Optional

from .models import ConnectionType, DeviceDescriptor, DeviceRegistration, DeviceStatus


class InventoryService:
    """Persisted inventory that generates and tracks device registrations."""

    def __init__(self, storage_path: Optional[pathlib.Path] = None) -> None:
        self._storage_path = storage_path
        self._lock = threading.Lock()
        self._registrations: Dict[str, DeviceRegistration] = {}
        if storage_path and storage_path.exists():
            self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load(self) -> None:
        raw = json.loads(self._storage_path.read_text())
        for u_sha, payload in raw.items():
            descriptor = DeviceDescriptor(
                vendor=payload["descriptor"]["vendor"],
                product=payload["descriptor"]["product"],
                connection=ConnectionType(payload["descriptor"]["connection"]),
                identifiers=payload["descriptor"].get("identifiers", {}),
                metadata=payload["descriptor"].get("metadata", {}),
            )
            status_raw = payload.get("status", DeviceStatus.PENDING_VALIDATION.value)
            try:
                status = DeviceStatus(status_raw)
            except ValueError:
                status = DeviceStatus.PENDING_VALIDATION
            self._registrations[u_sha] = DeviceRegistration(
                descriptor=descriptor,
                u_sha=u_sha,
                status=status,
                profiles=payload.get("profiles", []),
                assigned_hosts=payload.get("assigned_hosts", []),
            )

    def _save(self) -> None:
        if not self._storage_path:
            return
        payload = {
            u_sha: {
                "descriptor": {
                    **asdict(reg.descriptor),
                    "connection": reg.descriptor.connection.value,
                },
                "status": reg.status.value,
                "profiles": reg.profiles,
                "assigned_hosts": reg.assigned_hosts,
            }
            for u_sha, reg in self._registrations.items()
        }
        self._storage_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def register(self, descriptor: DeviceDescriptor) -> DeviceRegistration:
        """Register a device, creating a new `DeviceRegistration` when needed."""

        u_sha = self.compute_u_sha(descriptor)
        with self._lock:
            registration = self._registrations.get(u_sha)
            if registration is None:
                registration = DeviceRegistration(
                    descriptor=descriptor,
                    u_sha=u_sha,
                    status=DeviceStatus.PENDING_VALIDATION,
                )
                self._registrations[u_sha] = registration
                self._save()
            else:
                registration.status = DeviceStatus.ACTIVE
                self._save()
            return registration

    def update_status(self, u_sha: str, status: DeviceStatus) -> None:
        with self._lock:
            if u_sha in self._registrations:
                self._registrations[u_sha].status = status
                self._save()

    def attach_profiles(self, u_sha: str, profiles: Iterable[str]) -> None:
        with self._lock:
            if u_sha in self._registrations:
                unique = {
                    *self._registrations[u_sha].profiles,
                    *profiles,
                }
                self._registrations[u_sha].profiles = sorted(unique)
                self._save()

    def assign_hosts(self, u_sha: str, hosts: Iterable[str]) -> None:
        with self._lock:
            if u_sha in self._registrations:
                unique = {
                    *self._registrations[u_sha].assigned_hosts,
                    *hosts,
                }
                self._registrations[u_sha].assigned_hosts = sorted(unique)
                self._save()

    def get(self, u_sha: str) -> Optional[DeviceRegistration]:
        return self._registrations.get(u_sha)

    def items(self):
        return list(self._registrations.items())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def compute_u_sha(self, descriptor: DeviceDescriptor) -> str:
        payload = json.dumps(descriptor.canonical_payload(), sort_keys=True)
        return sha256(payload.encode("utf-8")).hexdigest()
