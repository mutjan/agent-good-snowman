#!/usr/bin/env python3
"""Send movement keys to A Good Snowman Is Hard To Build."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from snowman_config import load_config
from snowman_read_state import build_state, compact_state, compact_state_lines, diff_state_lines

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
            valid = ", ".join(sorted(set(KEY_CODES) | set(ALIASES)))
            raise SystemExit(f"Unknown move '{name}'. Valid moves: {valid}")
        try:
            repeat = int(count)
        except ValueError as exc:
            raise SystemExit(f"Invalid repeat count in '{token}'") from exc
        if repeat < 1:
            raise SystemExit(f"Repeat count must be positive in '{token}'")
        moves.extend([name] * repeat)
    return moves


def apple_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def activate_game(app_name: str) -> None:
    quoted = apple_quote(app_name)
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "System Events" to set frontmost of process "{quoted}" to true',
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["osascript", "-e", f'tell application "{quoted}" to activate'],
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


def send_with_process_applescript(moves: list[str], delay: float, app_name: str) -> None:
    quoted = apple_quote(app_name)
    for move in moves:
        subprocess.run(
            [
                "osascript",
                "-e",
                (
                    'tell application "System Events" to tell process '
                    f'"{quoted}" to key code {KEY_CODES[move]}'
                ),
            ],
            check=True,
        )
        time.sleep(delay)


def send_moves(
    moves: list[str],
    *,
    method: str,
    delay: float,
    hold_ms: int,
    app_name: str,
) -> None:
    if method == "cgevent":
        send_with_cgevent(moves, delay, hold_ms)
    elif method == "applescript":
        send_with_applescript(moves, delay)
    else:
        send_with_process_applescript(moves, delay, app_name)


def read_state(config: object, progress: Path | None, resources: Path | None) -> dict[str, object]:
    args = SimpleNamespace(
        progress=progress or config.progress_path,
        resources=resources or config.resources_dir,
        level=None,
        no_grid=True,
    )
    return build_state(args)


def print_observed_state(prefix: str, state: dict[str, object]) -> None:
    print(prefix)
    for line in compact_state_lines(state):
        print(f"  {line}")


def state_fingerprint(state: dict[str, object]) -> str:
    return json.dumps(compact_state(state), ensure_ascii=False, sort_keys=True)


def wait_for_observed_state(
    before: dict[str, object],
    *,
    config: object,
    progress: Path | None,
    resources: Path | None,
    observe_delay: float,
    observe_timeout: float,
    observe_poll: float,
) -> dict[str, object]:
    time.sleep(observe_delay)
    before_fingerprint = state_fingerprint(before)
    last = read_state(config, progress, resources)
    last_fingerprint = state_fingerprint(last)
    changed = last_fingerprint != before_fingerprint
    stable_reads = 0
    deadline = time.monotonic() + observe_timeout

    while time.monotonic() < deadline:
        time.sleep(observe_poll)
        current = read_state(config, progress, resources)
        current_fingerprint = state_fingerprint(current)
        if current_fingerprint == last_fingerprint:
            stable_reads += 1
            if changed and stable_reads >= 2:
                break
            continue

        last = current
        last_fingerprint = current_fingerprint
        changed = changed or current_fingerprint != before_fingerprint
        stable_reads = 0

    return last


def send_with_observe(
    moves: list[str],
    *,
    method: str,
    delay: float,
    observe_delay: float,
    observe_timeout: float,
    observe_poll: float,
    hold_ms: int,
    app_name: str,
    config: object,
    progress: Path | None,
    resources: Path | None,
) -> None:
    print_observed_state("before:", read_state(config, progress, resources))
    for index, move in enumerate(moves, start=1):
        before = read_state(config, progress, resources)
        send_moves([move], method=method, delay=0, hold_ms=hold_ms, app_name=app_name)
        after = wait_for_observed_state(
            before,
            config=config,
            progress=progress,
            resources=resources,
            observe_delay=observe_delay,
            observe_timeout=observe_timeout,
            observe_poll=observe_poll,
        )
        print(f"after[{index}] move={move}:")
        for line in diff_state_lines(before, after):
            print(f"  {line}")
    time.sleep(delay)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "moves",
        help="Moves such as 'right*3,up,left' or 'e*3,u,left'. Use reset/r for R and undo/z for Z.",
    )
    parser.add_argument("--config", type=Path, help="Path to snowman_config.json")
    parser.add_argument("--app-name", help="macOS app/process name")
    parser.add_argument("--progress", type=Path, help="Override progress.json path for --observe")
    parser.add_argument("--resources", type=Path, help="Override resources directory for --observe")
    parser.add_argument("--delay", type=float, help="Delay between keys")
    parser.add_argument("--hold-ms", type=int, help="Milliseconds to hold each key")
    parser.add_argument("--pre-delay", type=float, help="Delay after activation")
    parser.add_argument("--observe", action="store_true", help="Read state before and after each sent key")
    parser.add_argument("--observe-delay", type=float, help="Delay before reading state after each key")
    parser.add_argument("--observe-timeout", type=float, help="Maximum extra seconds to wait for observed state")
    parser.add_argument("--observe-poll", type=float, help="Seconds between observed-state polls")
    parser.add_argument("--no-activate", action="store_true", help="Do not focus the game first")
    parser.add_argument("--dry-run", action="store_true", help="Print moves without sending")
    parser.add_argument(
        "--method",
        choices=["process-applescript", "cgevent", "applescript"],
        default="process-applescript",
        help="Input method. process-applescript targets the Snowman process directly.",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    app_name = args.app_name or config.app_name or APP_NAME
    delay = args.delay if args.delay is not None else config.input_delay
    hold_ms = args.hold_ms if args.hold_ms is not None else config.hold_ms
    pre_delay = args.pre_delay if args.pre_delay is not None else config.pre_delay
    observe_delay = args.observe_delay if args.observe_delay is not None else min(delay, 0.3)
    observe_timeout = args.observe_timeout if args.observe_timeout is not None else max(1.5, delay * 3)
    observe_poll = args.observe_poll if args.observe_poll is not None else 0.2

    moves = parse_moves(args.moves)
    print("moves=" + ",".join(moves))
    if args.dry_run:
        return 0

    if not args.no_activate:
        activate_game(app_name)
        time.sleep(pre_delay)

    if args.observe:
        send_with_observe(
            moves,
            method=args.method,
            delay=delay,
            observe_delay=observe_delay,
            observe_timeout=observe_timeout,
            observe_poll=observe_poll,
            hold_ms=hold_ms,
            app_name=app_name,
            config=config,
            progress=args.progress,
            resources=args.resources,
        )
    else:
        send_moves(moves, method=args.method, delay=delay, hold_ms=hold_ms, app_name=app_name)

    print("frontmost=" + frontmost_process())
    return 0


if __name__ == "__main__":
    sys.exit(main())
