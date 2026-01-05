from __future__ import annotations

import json
import pathlib

from mayan_sync_control.inventory import InventoryService
from mayan_sync_control.models import ConnectionType, DeviceDescriptor, DeviceStatus


def make_descriptor(**kwargs):
    defaults = dict(
        vendor="Akai",
        product="APC40",
        connection=ConnectionType.USB,
        identifiers={"serial": "ABC123"},
    )
    defaults.update(kwargs)
    return DeviceDescriptor(**defaults)


def test_register_and_persist(tmp_path: pathlib.Path) -> None:
    storage = tmp_path / "inventory.json"
    inventory = InventoryService(storage_path=storage)
    descriptor = make_descriptor()
    registration = inventory.register(descriptor)
    assert registration.status == DeviceStatus.PENDING_VALIDATION
    inventory.update_status(registration.u_sha, DeviceStatus.ACTIVE)
    inventory.attach_profiles(registration.u_sha, ["default"])
    inventory.assign_hosts(registration.u_sha, ["house"])

    # Ensure persisted data matches expectations
    reloaded = json.loads(storage.read_text())
    payload = reloaded[registration.u_sha]
    assert payload["descriptor"]["vendor"] == "Akai"
    assert payload["descriptor"]["connection"] == "usb"
    assert payload["profiles"] == ["default"]
    assert payload["assigned_hosts"] == ["house"]

    # Re-open service to ensure load works
    inventory_reloaded = InventoryService(storage_path=storage)
    registration_reloaded = inventory_reloaded.get(registration.u_sha)
    assert registration_reloaded is not None
    assert registration_reloaded.descriptor.vendor == "Akai"
    assert registration_reloaded.status == DeviceStatus.ACTIVE


def test_compute_u_sha_is_stable() -> None:
    descriptor = make_descriptor(metadata={"profile": "studio"})
    inventory = InventoryService()
    first = inventory.compute_u_sha(descriptor)
    second = inventory.compute_u_sha(descriptor)
    assert first == second
