from __future__ import annotations

import asyncio

from mayan_sync_control.agent import Agent, DeviceEvent, LoopbackMonitor
from mayan_sync_control.inventory import InventoryService
from mayan_sync_control.models import AgentConfig, ConnectionType, DeviceDescriptor, Host, RoutingMode
from mayan_sync_control.router import Router


def make_agent(loopback: LoopbackMonitor | None = None) -> tuple[Agent, LoopbackMonitor]:
    monitor = loopback or LoopbackMonitor()
    inventory = InventoryService()
    router = Router()
    config = AgentConfig(hosts=[Host(host_id="main", label="Main", priority=10)])
    agent = Agent(inventory, router, monitors=[monitor], config=config)
    return agent, monitor


def test_agent_registers_and_routes_device() -> None:
    agent, monitor = make_agent()
    descriptor = DeviceDescriptor(
        vendor="Pioneer",
        product="DDJ-REV1",
        connection=ConnectionType.USB,
        metadata={"routing_mode": RoutingMode.PRIMARY.value},
    )
    monitor.push(DeviceEvent(descriptor, connected=True))

    async def run_once():
        task = asyncio.create_task(agent.run())
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(run_once())
    finally:
        loop.close()

    registration = agent.inventory.get(agent.inventory.compute_u_sha(descriptor))
    assert registration is not None
    assert registration.status.name == "ACTIVE"
    assignments = agent.router.list_assignments()
    assert registration.u_sha in assignments
    assert assignments[registration.u_sha][0].host_id == "main"
