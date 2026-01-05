"""CLI entrypoint for Mayan Sync Control agent."""

from __future__ import annotations

import argparse
import asyncio
import logging
import pathlib

from .agent import Agent


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Mayan Sync Control agent")
    parser.add_argument("config", type=pathlib.Path, help="JSON configuration file")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)
    agent = Agent.from_config(args.config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(agent.run())
    except KeyboardInterrupt:  # pragma: no cover - interactive usage
        return 0
    finally:
        loop.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
