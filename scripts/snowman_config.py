#!/usr/bin/env python3
"""Shared local configuration for Snowman control scripts."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "snowman_config.json"
EXAMPLE_CONFIG_PATH = ROOT / "snowman_config.example.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "game_app": (
        "~/Library/Application Support/Steam/steamapps/common/"
        "A Good Snowman Is Hard To Build/Snowman.app"
    ),
    "save_dir": "~/Library/Application Support/A Good Snowman Is Hard To Build",
    "app_name": "Snowman",
    "input_delay": 0.45,
    "hold_ms": 115,
    "pre_delay": 0.8,
}


@dataclass(frozen=True)
class SnowmanConfig:
    config_path: Path
    game_app: Path
    save_dir: Path
    app_name: str
    input_delay: float
    hold_ms: int
    pre_delay: float

    @property
    def resources_dir(self) -> Path:
        return self.game_app / "Contents" / "Resources" / "resources"

    @property
    def progress_path(self) -> Path:
        return self.save_dir / "progress.json"

    @property
    def game_files_found(self) -> bool:
        return (self.resources_dir / "levels.txt").exists() and (self.resources_dir / "layout.txt").exists()

    @property
    def save_file_found(self) -> bool:
        return self.progress_path.exists()


def expand_path(value: str) -> Path:
    return Path(value).expanduser()


def config_path(path: Path | None = None) -> Path:
    if path is not None:
        return path.expanduser()
    env_path = os.environ.get("SNOWMAN_CONFIG")
    return Path(env_path).expanduser() if env_path else DEFAULT_CONFIG_PATH


def load_raw_config(path: Path, *, create: bool = False) -> dict[str, Any]:
    if path.exists():
        data = json.loads(path.read_text())
    elif create:
        path.parent.mkdir(parents=True, exist_ok=True)
        if EXAMPLE_CONFIG_PATH.exists():
            shutil.copy2(EXAMPLE_CONFIG_PATH, path)
            data = json.loads(path.read_text())
        else:
            data = dict(DEFAULT_CONFIG)
            path.write_text(json.dumps(data, indent=2) + "\n")
    else:
        data = {}
    return {**DEFAULT_CONFIG, **data}


def load_config(path: Path | None = None, *, create: bool = False) -> SnowmanConfig:
    resolved_path = config_path(path)
    raw = load_raw_config(resolved_path, create=create)
    return SnowmanConfig(
        config_path=resolved_path,
        game_app=expand_path(str(raw["game_app"])),
        save_dir=expand_path(str(raw["save_dir"])),
        app_name=str(raw["app_name"]),
        input_delay=float(raw["input_delay"]),
        hold_ms=int(raw["hold_ms"]),
        pre_delay=float(raw["pre_delay"]),
    )


def print_status(config: SnowmanConfig) -> None:
    print(f"config_path={config.config_path}")
    print(f"game_app={config.game_app}")
    print(f"resources_dir={config.resources_dir}")
    print(f"save_dir={config.save_dir}")
    print(f"progress_path={config.progress_path}")
    print(f"app_name={config.app_name}")
    print(f"input_delay={config.input_delay}")
    print(f"hold_ms={config.hold_ms}")
    print(f"pre_delay={config.pre_delay}")
    print(f"game_files_found={config.game_files_found}")
    print(f"save_file_found={config.save_file_found}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Path to snowman_config.json")
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create a local config from snowman_config.example.json if missing.",
    )
    args = parser.parse_args()
    config = load_config(args.config, create=args.create)
    if args.create and not config.config_path.exists():
        raise SystemExit(f"Could not create config at {config.config_path}")
    print_status(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
