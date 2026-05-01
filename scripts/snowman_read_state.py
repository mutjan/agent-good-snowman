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
PASSIVE_ENTITY_TYPES = {"player", "grass"}
Coord = tuple[int, int]


@dataclass(frozen=True)
class LevelInfo:
    index: int
    name: str
    grid: tuple[str, ...]
    initial_player: Coord | None
    initial_balls: tuple[dict[str, Any], ...]


INITIAL_MARKER_INFO: dict[str, dict[str, Any]] = {
    "1": {
        "label": "small",
        "stack_bottom_to_top": ["small"],
        "note": "Static marker 1 is a single small snowball.",
    },
    "2": {
        "label": "medium",
        "stack_bottom_to_top": ["medium"],
        "note": "Static marker 2 is a single medium snowball.",
    },
    "3": {
        "label": "small_on_medium",
        "stack_bottom_to_top": ["medium", "small"],
        "note": "Static marker 3 is a pre-stacked medium snowball with a small snowball on top, not numeric size 3.",
    },
    "4": {
        "label": "large",
        "stack_bottom_to_top": ["large"],
        "note": "Static marker 4 is a single large snowball.",
    },
}


def initial_marker_info(marker: str) -> dict[str, Any]:
    info = INITIAL_MARKER_INFO.get(marker)
    if info is None:
        return {
            "marker": marker,
            "label": f"initial_marker_{marker}",
            "stack_bottom_to_top": [],
            "note": "Unknown static resource marker; inspect live entities after interacting with it.",
        }
    return {"marker": marker, **info}


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
        balls: list[dict[str, Any]] = []

        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch in "pPq":
                    player = (x, y)
                elif ch.isdigit():
                    balls.append({"x": x, "y": y, **initial_marker_info(ch)})

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


def current_objects(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for entity in entities:
        entity_type = entity.get("type")
        x = entity.get("x")
        y = entity.get("y")
        if entity_type in PASSIVE_ENTITY_TYPES:
            continue
        if not isinstance(entity_type, str) or not isinstance(x, int) or not isinstance(y, int):
            continue
        item: dict[str, Any] = {
            "id": entity.get("id"),
            "type": entity_type,
            "x": x,
            "y": y,
        }
        if "views" in entity:
            item["views"] = entity["views"]
        objects.append(item)
    return objects


def state_notes() -> list[str]:
    return [
        "initial_balls and initial_player come from static level resources; they are not live positions after play begins.",
        "initial_balls.marker is a resource marker, not a numeric size. Use label and stack_bottom_to_top for known markers.",
        "Level 0 (Lucy) starts with marker 3: a medium snowball with a small snowball stacked on top.",
        "After pushing a marker 3 stack, seeing a live small object plus a small_on_medium grass view is expected stack transition state, not a medium ball shrinking.",
        "entities are the saved live objects. The player and moved balls appear there; unchanged initial balls may be absent until touched.",
        "grass entities record consumed snow/roll history. They are useful context but are not movable objects.",
        "grid digits are static initial ball markers. Treat them as a level reference, not as proof of current live occupancy after any move.",
    ]


def agent_guidance(state: dict[str, Any] | None = None) -> list[str]:
    guidance = [
        "Do not stop after reading state when the current level is incomplete.",
        "Choose a small candidate move batch and run: python3 scripts/snowman_send_keys.py '<moves>' --observe",
        "Use one to five moves per observed batch while learning mechanics; increase --observe-timeout for pushes or animations.",
        "This harness intentionally provides no solution route or solver output.",
    ]
    if state is not None and state.get("current_completed"):
        guidance[0] = "The current saved level is completed; continue by navigating in-game with observed movement."
    return guidance


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
    entities = sorted_entities(level_entry)

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
        "current_objects": current_objects(entities),
        "entities": entities,
        "initial_player": coord_list(level_info.initial_player) if level_info else None,
        "initial_balls": list(level_info.initial_balls) if level_info else [],
        "state_notes": state_notes(),
    }
    state["agent_guidance"] = agent_guidance(state)
    if not args.no_grid:
        state["grid"] = list(level_info.grid) if level_info else []
    return state


def coord_text(value: Any) -> str:
    if isinstance(value, list) and len(value) == 2:
        return f"{value[0]},{value[1]}"
    return "none"


def stack_text(value: Any) -> str:
    if isinstance(value, list) and value:
        return "+".join(str(item) for item in value)
    return "unknown"


def initial_ball_text(item: dict[str, Any]) -> str:
    return (
        f"marker={item.get('marker')} "
        f"label={item.get('label', 'unknown')} "
        f"stack={stack_text(item.get('stack_bottom_to_top'))} "
        f"at {item.get('x')},{item.get('y')}"
    )


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

    print("current_objects:")
    for item in state["current_objects"]:
        item_id = item.get("id")
        item_type = item.get("type", "unknown")
        print(f"  {item_id} {item_type} {item.get('x')},{item.get('y')}")

    print("entities:")
    for entity in state["entities"]:
        entity_id = entity.get("id")
        entity_type = entity.get("type", "unknown")
        pos = coord_text([entity.get("x"), entity.get("y")])
        extra = ""
        if "views" in entity:
            extra = " views=" + json.dumps(entity["views"], separators=(",", ":"))
        print(f"  {entity_id} {entity_type} {pos}{extra}")

    print("static_initial_balls:")
    for item in state["initial_balls"]:
        print(f"  {initial_ball_text(item)}")

    if "grid" in state:
        print("grid:")
        for row in state["grid"]:
            print(f"  {row}")


def compact_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": state.get("timestamp"),
        "level": state.get("level"),
        "level_name": state.get("level_name"),
        "player": state.get("player"),
        "reset": state.get("reset"),
        "current_completed": state.get("current_completed"),
        "completed_count": state.get("completed_count"),
        "current_objects": state.get("current_objects", []),
        "snowmen": state.get("snowmen", []),
        "initial_player": state.get("initial_player"),
        "initial_balls": state.get("initial_balls", []),
        "state_notes": state.get("state_notes", []),
        "agent_guidance": state.get("agent_guidance", []),
    }


def compact_state_lines(state: dict[str, Any]) -> list[str]:
    lines = [
        (
            f"level={state.get('level')} "
            f"name={state.get('level_name') or 'unknown'} "
            f"completed={state.get('current_completed')} "
            f"timestamp={state.get('timestamp')}"
        ),
        f"player={coord_text(state.get('player'))} reset={coord_text(state.get('reset'))}",
    ]

    objects = state.get("current_objects", [])
    if objects:
        lines.append("current_objects:")
        for item in objects:
            lines.append(f"  {item.get('id')} {item.get('type')} {item.get('x')},{item.get('y')}")
    else:
        lines.append("current_objects: none")

    snowmen = state.get("snowmen", [])
    if snowmen:
        lines.append("snowmen:")
        for item in snowmen:
            lines.append(
                "  "
                f"index={item.get('index')} "
                f"pos={item.get('x')},{item.get('y')} "
                f"hugged={item.get('hugged')}"
            )

    initial_balls = state.get("initial_balls", [])
    if initial_balls:
        lines.append("static_initial_balls:")
        for item in initial_balls:
            lines.append(f"  {initial_ball_text(item)}")
        lines.append(
            "hint: current_objects only lists saved live objects; untouched static_initial_balls may still occupy their cells."
        )
    guidance = state.get("agent_guidance", [])
    if guidance:
        lines.append("agent_guidance:")
        for item in guidance:
            lines.append(f"  {item}")
    return lines


def object_key(item: dict[str, Any]) -> str:
    item_id = item.get("id")
    if item_id is not None:
        return str(item_id)
    return f"{item.get('type')}@{item.get('x')},{item.get('y')}"


def diff_state_lines(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in ("timestamp", "level", "level_name", "current_completed"):
        if before.get(key) != after.get(key):
            lines.append(f"{key}: {before.get(key)} -> {after.get(key)}")

    if before.get("player") != after.get("player"):
        lines.append(f"player: {coord_text(before.get('player'))} -> {coord_text(after.get('player'))}")

    before_objects = {object_key(item): item for item in before.get("current_objects", [])}
    after_objects = {object_key(item): item for item in after.get("current_objects", [])}
    for key in sorted(before_objects.keys() - after_objects.keys()):
        item = before_objects[key]
        lines.append(f"removed: {item.get('type')} {item.get('x')},{item.get('y')} id={item.get('id')}")
    for key in sorted(after_objects.keys() - before_objects.keys()):
        item = after_objects[key]
        lines.append(f"added: {item.get('type')} {item.get('x')},{item.get('y')} id={item.get('id')}")
    for key in sorted(before_objects.keys() & after_objects.keys()):
        old = before_objects[key]
        new = after_objects[key]
        old_pos = (old.get("x"), old.get("y"))
        new_pos = (new.get("x"), new.get("y"))
        if old.get("type") != new.get("type") or old_pos != new_pos:
            lines.append(
                f"object {key}: {old.get('type')} {old_pos[0]},{old_pos[1]} "
                f"-> {new.get('type')} {new_pos[0]},{new_pos[1]}"
            )

    if not lines:
        return [
            "no saved state change",
            "hint: the move may be blocked, may only have changed transient push state, or may need a longer --observe-timeout.",
        ]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Path to snowman_config.json")
    parser.add_argument("--progress", type=Path, help="Override progress.json path")
    parser.add_argument("--resources", type=Path, help="Override resources directory")
    parser.add_argument("--level", type=int, help="Inspect a saved level instead of the current level")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--compact", action="store_true", help="Print a concise state summary")
    parser.add_argument("--explain", action="store_true", help="Print notes about static versus live state")
    parser.add_argument("--no-grid", action="store_true", help="Omit the static level grid")
    args = parser.parse_args()

    config = load_config(args.config)
    args.progress = args.progress or config.progress_path
    args.resources = args.resources or config.resources_dir

    state = build_state(args)
    if args.json:
        data = compact_state(state) if args.compact else state
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.compact:
        print("\n".join(compact_state_lines(state)))
        if args.explain:
            print("notes:")
            for note in state_notes():
                print(f"  {note}")
    else:
        print_text(state)
        if args.explain:
            print("notes:")
            for note in state_notes():
                print(f"  {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
