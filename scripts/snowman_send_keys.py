#!/usr/bin/env python3
"""Send movement keys to A Good Snowman Is Hard To Build."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from snowman_config import load_config

APP_NAME = "Snowman"

KEY_CODES = {
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
    "undo": 6,
    "z": 6,
    "restart": 15,
    "reset": 15,
    "r": 15,
    "confirm": 49,
    "space": 49,
    "enter": 36,
    "return": 36,
    "escape": 53,
    "esc": 53,
}

ALIASES = {
    "l": "left",
    "h": "left",
    "west": "left",
    "w": "up",
    "u": "up",
    "k": "up",
    "north": "up",
    "s": "down",
    "d": "down",
    "j": "down",
    "south": "down",
    "e": "right",
    "east": "right",
    "rt": "right",
    "rgt": "right",
    "q": "esc",
}


def parse_moves(raw: str) -> list[str]:
    moves: list[str] = []
    normalized = raw.replace("\n", ",").replace(" ", ",")
    for chunk in normalized.split(","):
        token = chunk.strip().lower()
        if not token:
            continue
        if "*" in token:
            name, count = token.split("*", 1)
        else:
            name, count = token, "1"
        name = ALIASES.get(name, name)
        if name not in KEY_CODES:
            valid = ", ".join(sorted(KEY_CODES | ALIASES.keys()))
            raise SystemExit(f"Unknown move '{name}'. Valid moves: {valid}")
        try:
            repeat = int(count)
        except ValueError as exc:
            raise SystemExit(f"Invalid repeat count in '{token}'") from exc
        if repeat < 1:
            raise SystemExit(f"Repeat count must be positive in '{token}'")
        moves.extend([name] * repeat)
    return moves


def activate_game(app_name: str) -> None:
    subprocess.run(
        ["osascript", "-e", f'tell application "{app_name}" to activate'],
        check=True,
    )


def frontmost_process() -> str:
    result = subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to name of first process whose frontmost is true',
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def ensure_cgevent_helper() -> Path:
    root = Path(__file__).resolve().parent
    source = root / "snowman_cgevent_keys.c"
    binary = root / "snowman_cgevent_keys"
    if binary.exists() and binary.stat().st_mtime >= source.stat().st_mtime:
        return binary
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-framework",
            "ApplicationServices",
            str(source),
            "-o",
            str(binary),
        ],
        check=True,
    )
    return binary


def send_with_cgevent(moves: list[str], delay: float, hold_ms: int) -> None:
    binary = ensure_cgevent_helper()
    subprocess.run(
        [
            str(binary),
            "--delay-ms",
            str(int(delay * 1000)),
            "--hold-ms",
            str(hold_ms),
            *moves,
        ],
        check=True,
    )


def send_with_applescript(moves: list[str], delay: float) -> None:
    for move in moves:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "System Events" to key code {KEY_CODES[move]}',
            ],
            check=True,
        )
        time.sleep(delay)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "moves",
        help="Moves such as 'right*3,up,left' or 'e*3,u,left'. Use reset/r for R and undo/z for Z.",
    )
    parser.add_argument("--config", type=Path, help="Path to snowman_config.json")
    parser.add_argument("--app-name", help="macOS app/process name")
    parser.add_argument("--delay", type=float, help="Delay between keys")
    parser.add_argument("--hold-ms", type=int, help="Milliseconds to hold each key")
    parser.add_argument("--pre-delay", type=float, help="Delay after activation")
    parser.add_argument("--no-activate", action="store_true", help="Do not focus the game first")
    parser.add_argument("--dry-run", action="store_true", help="Print moves without sending")
    parser.add_argument(
        "--method",
        choices=["cgevent", "applescript"],
        default="cgevent",
        help="Input method. cgevent posts HID-level events and is the verified path.",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    app_name = args.app_name or config.app_name or APP_NAME
    delay = args.delay if args.delay is not None else config.input_delay
    hold_ms = args.hold_ms if args.hold_ms is not None else config.hold_ms
    pre_delay = args.pre_delay if args.pre_delay is not None else config.pre_delay

    moves = parse_moves(args.moves)
    print("moves=" + ",".join(moves))
    if args.dry_run:
        return 0

    if not args.no_activate:
        activate_game(app_name)
        time.sleep(pre_delay)

    if args.method == "cgevent":
        send_with_cgevent(moves, delay, hold_ms)
    else:
        send_with_applescript(moves, delay)

    print("frontmost=" + frontmost_process())
    return 0


if __name__ == "__main__":
    sys.exit(main())
