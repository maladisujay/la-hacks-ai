"""Start all five agents.

    uv run python -m strata_agents.run            # one Bureau, messages between agents stay in-process
    uv run python -m strata_agents.run --only concierge   # one agent per process (separate hosts)
"""

from __future__ import annotations

import argparse

from uagents import Bureau

from .agents.concierge import concierge
from .agents.workers import checkout, curator, ledger, renderer

AGENTS = {"concierge": concierge, "curator": curator, "renderer": renderer, "checkout": checkout, "ledger": ledger}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=list(AGENTS), help="run a single agent on its own port (8001-8005)")
    parser.add_argument("--port", type=int, default=8000, help="Bureau port")
    args = parser.parse_args()

    for name, agent in AGENTS.items():
        print(f"{name:10s} {agent.address}")

    if args.only:
        # One process per agent gives each its own inspector URL for Connect → Mailbox.
        AGENTS[args.only].run()
        return

    bureau = Bureau(port=args.port)
    for agent in AGENTS.values():
        bureau.add(agent)
    bureau.run()


if __name__ == "__main__":
    main()
