from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

import uvicorn

from strix_console_service.app import create_app


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the minimal development server arguments."""

    parser = argparse.ArgumentParser(description="Run the Strix Console control service")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1"])
    parser.add_argument("--port", default=43110, type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the loopback-only service."""

    args = parse_args(argv)
    access_token = os.environ.get("STRIX_CONSOLE_ACCESS_TOKEN")
    bootstrap_token = os.environ.get("STRIX_CONSOLE_BOOTSTRAP_TOKEN")
    uvicorn.run(
        create_app(access_token=access_token, bootstrap_token=bootstrap_token),
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
