from __future__ import annotations

import argparse
import os
import threading
import time
from collections.abc import Sequence

import uvicorn

from strix_console_service.app import create_app


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the minimal development server arguments."""

    parser = argparse.ArgumentParser(description="Run the Strix Console control service")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1"])
    parser.add_argument("--port", default=43110, type=int)
    parser.add_argument("--parent-pid", type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the loopback-only service."""

    args = parse_args(argv)
    if args.parent_pid:
        threading.Thread(
            target=_exit_when_parent_stops,
            args=(args.parent_pid,),
            name="strix-console-parent-watch",
            daemon=True,
        ).start()
    access_token = os.environ.get("STRIX_CONSOLE_ACCESS_TOKEN")
    bootstrap_token = os.environ.get("STRIX_CONSOLE_BOOTSTRAP_TOKEN")
    uvicorn.run(
        create_app(access_token=access_token, bootstrap_token=bootstrap_token),
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=False,
    )


def _exit_when_parent_stops(parent_pid: int) -> None:
    if os.name == "nt":
        _wait_for_windows_parent_exit(parent_pid)
        os._exit(0)

    while True:
        try:
            os.kill(parent_pid, 0)
        except OSError:
            os._exit(0)
        time.sleep(1)


def _wait_for_windows_parent_exit(parent_pid: int) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait_for_single_object.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    synchronize = 0x00100000
    infinite = 0xFFFFFFFF
    handle = open_process(synchronize, False, parent_pid)
    if not handle:
        return
    try:
        wait_for_single_object(handle, infinite)
    finally:
        close_handle(handle)


if __name__ == "__main__":
    main()
