from __future__ import annotations

from mayan_sync_control.models import Host, RoutingMode
from mayan_sync_control.router import Router


def test_assignments_sorted_by_priority() -> None:
    router = Router()
    router.register_hosts(
        [
            Host(host_id="studio", label="Studio", priority=10),
            Host(host_id="backup", label="Backup", priority=5),
        ]
    )
    router.assign("device", "backup", RoutingMode.MIRROR)
    router.assign("device", "studio", RoutingMode.PRIMARY)
    assignments = router.list_assignments()["device"]
    assert [assignment.host_id for assignment in assignments] == ["studio", "backup"]


def test_release_device() -> None:
    router = Router()
    router.register_host(Host(host_id="main", label="Main"))
    router.assign("device", "main", RoutingMode.PRIMARY)
    router.release_device("device")
    assert router.list_assignments() == {}
