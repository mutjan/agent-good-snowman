#!/usr/bin/env python3
"""Read-only state reporter for A Good Snowman Is Hard To Build.

This script reads the game's save file and bundled resource files. It does not
solve levels, replay routes, patch saves, inspect memory, or attach to the game
process.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from snowman_config import load_config


GRID_CHARS = set("#x.'.pPq012345")
Coord = tuple[int, int]


@dataclass(frozen=True)
class LevelInfo:
    index: int
    name: str
    grid: tuple[str, ...]
    initial_player: Coord | None
    initial_balls: tuple[dict[str, int], ...]


def is_grid_line(line: str) -> bool:
    return bool(line) and set(line) <= GRID_CHARS and any(ch in line for ch in "#x")


def parse_levels(path: Path) -> list[LevelInfo]:
    if not path.exists():
        return []

    levels: list[LevelInfo] = []
    blocks = [block.strip("\n") for block in path.read_text().split("\n\n") if block.strip()]
    for index, block in enumerate(blocks):
        lines = block.splitlines()
        name = lines[0].strip() if lines else f"level-{index}"
        grid = tuple(line for line in lines[1:] if is_grid_line(line))
        player: Coord | None = None
        balls: list[dict[str, int]] = []

        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch in "pPq":
                    player = (x, y)
                elif ch.isdigit():
                    balls.append({"x": x, "y": y, "size": int(ch)})

        levels.append(
            LevelInfo(
                index=index,
                name=name,
                grid=grid,
                initial_player=player,
                initial_balls=tuple(balls),
            )
        )
    return levels


def parse_layout(path: Path) -> dict[int, Coord | None]:
    if not path.exists():
        return {}

    entries: dict[int, Coord | None] = {}
    in_positions = False
    seen_entry = False
    for line in path.read_text().splitlines():
        raw = line.strip()
        if not raw:
            if in_positions and seen_entry:
                break
            continue
        if raw.startswith("LAYOUT VERSION"):
            in_positions = True
            continue
        if not in_positions:
            continue
        index = len(entries)
        if raw == "x":
            entries[index] = None
            seen_entry = True
            continue
        try:
            x_raw, y_raw = raw.split(",", 1)
            entries[index] = (int(x_raw), int(y_raw))
            seen_entry = True
        except ValueError:
            break
    return entries


def load_progress(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def sorted_entities(entry: dict[str, Any]) -> list[dict[str, Any]]:
    entities = entry.get("entities", {})
    if not isinstance(entities, dict):
        return []

    def key(item: tuple[str, Any]) -> tuple[int, str]:
        raw_id, _entity = item
        return (int(raw_id), raw_id) if raw_id.isdigit() else (10**9, raw_id)

    result: list[dict[str, Any]] = []
    for raw_id, entity in sorted(entities.items(), key=key):
        if isinstance(entity, dict):
            result.append({"id": raw_id, **entity})
    return result


def entity_coord(entity: dict[str, Any] | None) -> Coord | None:
    if not entity:
        return None
    x = entity.get("x")
    y = entity.get("y")
    if isinstance(x, int) and isinstance(y, int):
        return (x, y)
    return None


def coord_list(coord: Coord | None) -> list[int] | None:
    return [coord[0], coord[1]] if coord is not None else None


def build_state(args: argparse.Namespace) -> dict[str, Any]:
    progress = load_progress(args.progress)
    levels = parse_levels(args.resources / "levels.txt")
    layout = parse_layout(args.resources / "layout.txt")

    level_index = args.level if args.level is not None else int(progress.get("level", -1))
    level_entry = progress.get("levels", {}).get(str(level_index), {})
    level_info = levels[level_index] if 0 <= level_index < len(levels) else None

    player = entity_coord(level_entry.get("entities", {}).get("1"))
    reset = entity_coord({"x": level_entry.get("resetX"), "y": level_entry.get("resetY")})
    completed_levels = sorted(
        int(raw_id)
        for raw_id, item in progress.get("levels", {}).items()
        if raw_id.isdigit() and isinstance(item, dict) and item.get("completed")
    )

    state: dict[str, Any] = {
        "version": progress.get("version"),
        "timestamp": progress.get("timestamp"),
        "level": level_index,
        "level_name": level_info.name if level_info else None,
        "layout_coord": coord_list(layout.get(level_index)),
        "player": coord_list(player),
        "reset": coord_list(reset),
        "current_completed": bool(level_entry.get("completed")),
        "completed_count": len(completed_levels),
        "completed_levels": completed_levels,
        "snowmen": level_entry.get("snowmen", []),
        "entities": sorted_entities(level_entry),
        "initial_player": coord_list(level_info.initial_player) if level_info else None,
        "initial_balls": list(level_info.initial_balls) if level_info else [],
    }
    if not args.no_grid:
        state["grid"] = list(level_info.grid) if level_info else []
    return state


def coord_text(value: Any) -> str:
    if isinstance(value, list) and len(value) == 2:
        return f"{value[0]},{value[1]}"
    return "none"


def print_text(state: dict[str, Any]) -> None:
    print(f"level={state['level']}")
    print(f"level_name={state['level_name'] or 'unknown'}")
    print(f"layout_coord={coord_text(state['layout_coord'])}")
    print(f"player={coord_text(state['player'])}")
    print(f"reset={coord_text(state['reset'])}")
    print(f"current_completed={state['current_completed']}")
    print(f"completed_count={state['completed_count']}")
    print("completed_levels=" + ",".join(map(str, state["completed_levels"])))
    print("snowmen=" + json.dumps(state["snowmen"], ensure_ascii=False, separators=(",", ":")))

    print("entities:")
    for entity in state["entities"]:
        entity_id = entity.get("id")
        entity_type = entity.get("type", "unknown")
        pos = coord_text([entity.get("x"), entity.get("y")])
        extra = ""
        if "views" in entity:
            extra = " views=" + json.dumps(entity["views"], separators=(",", ":"))
        print(f"  {entity_id} {entity_type} {pos}{extra}")

    if "grid" in state:
        print("grid:")
        for row in state["grid"]:
            print(f"  {row}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Path to snowman_config.json")
    parser.add_argument("--progress", type=Path, help="Override progress.json path")
    parser.add_argument("--resources", type=Path, help="Override resources directory")
    parser.add_argument("--level", type=int, help="Inspect a saved level instead of the current level")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--no-grid", action="store_true", help="Omit the static level grid")
    args = parser.parse_args()

    config = load_config(args.config)
    args.progress = args.progress or config.progress_path
    args.resources = args.resources or config.resources_dir

    state = build_state(args)
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print_text(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
