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
LIVE_OBJECT_SYMBOLS = {
    "small": "s",
    "medium": "m",
    "large": "l",
    "snowman": "N",
    "snowman_head": "N",
    "snowman_middle": "N",
}
SNOWBALL_SIZE_BY_TYPE = {
    "small": "small",
    "snowman_head": "small",
    "medium": "medium",
    "snowman_middle": "medium",
    "large": "large",
    "snowman": "large",
}
SIZE_ORDER = ("small", "medium", "large")
Coord = tuple[int, int]


@dataclass(frozen=True)
class LevelInfo:
    index: int
    name: str
    target_snowmen: int | None
    grid: tuple[str, ...]
    initial_player: Coord | None
    initial_balls: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class LayoutInfo:
    positions: dict[int, Coord | None]
    objects: tuple[dict[str, Any], ...]


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
        target_snowmen: int | None = None
        for line in lines[1:]:
            raw = line.strip()
            if raw.isdigit():
                target_snowmen = int(raw)
                break
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
                target_snowmen=target_snowmen,
                grid=grid,
                initial_player=player,
                initial_balls=tuple(balls),
            )
        )
    return levels


def parse_layout(path: Path) -> LayoutInfo:
    if not path.exists():
        return LayoutInfo({}, ())

    entries: dict[int, Coord | None] = {}
    objects: list[dict[str, Any]] = []
    reading_positions = False
    seen_entry = False
    for line in path.read_text().splitlines():
        raw = line.strip()
        if not raw:
            if reading_positions and seen_entry:
                reading_positions = False
            continue
        if raw.startswith("LAYOUT VERSION"):
            reading_positions = True
            continue
        if reading_positions:
            index = len(entries)
            if raw == "x":
                entries[index] = None
                seen_entry = True
                continue
            try:
                x_raw, y_raw = raw.split(",", 1)
                entries[index] = (int(x_raw), int(y_raw))
                seen_entry = True
                continue
            except ValueError:
                reading_positions = False

        parts = raw.split(",")
        if len(parts) < 3:
            continue
        try:
            x = int(parts[1])
            y = int(parts[2])
        except ValueError:
            continue
        objects.append({"kind": parts[0], "x": x, "y": y})
    return LayoutInfo(entries, tuple(objects))


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


def empty_inventory() -> dict[str, int]:
    return {size: 0 for size in SIZE_ORDER}


def initial_inventory(initial_balls: tuple[dict[str, Any], ...]) -> dict[str, int]:
    counts = empty_inventory()
    for item in initial_balls:
        stack = item.get("stack_bottom_to_top")
        if not isinstance(stack, list):
            continue
        for size in stack:
            if size in counts:
                counts[size] += 1
    return counts


def live_inventory(objects: list[dict[str, Any]]) -> dict[str, int]:
    counts = empty_inventory()
    for item in objects:
        entity_type = item.get("type")
        size = SNOWBALL_SIZE_BY_TYPE.get(entity_type)
        if size is not None:
            counts[size] += 1
    return counts


def inventory_total(counts: dict[str, int]) -> int:
    return sum(counts.get(size, 0) for size in SIZE_ORDER)


def snowball_inventory(state: dict[str, Any], level_info: LevelInfo | None) -> dict[str, Any]:
    objects = [item for item in state.get("current_objects", []) if isinstance(item, dict)]
    live_counts = live_inventory(objects)
    initial_counts = initial_inventory(level_info.initial_balls if level_info else ())
    live_total = inventory_total(live_counts)
    initial_total = inventory_total(initial_counts)

    if live_total == 0:
        return {
            "source": "static_initial_balls",
            "reliable": True,
            "counts": initial_counts,
            "known_total": initial_total,
            "initial_total": initial_total,
            "note": "No saved live snowballs yet; inventory is read from static initial balls.",
        }

    reliable = initial_total == 0 or live_total >= initial_total
    return {
        "source": "current_objects",
        "reliable": reliable,
        "counts": live_counts,
        "known_total": live_total,
        "initial_total": initial_total,
        "note": (
            "All initial snowball units appear to be represented as saved live objects."
            if reliable
            else "Only saved live snowballs are counted; untouched static initial balls may still exist, so dead-state inference is withheld."
        ),
    }


def dead_state(state: dict[str, Any], level_info: LevelInfo | None) -> dict[str, Any]:
    target = level_info.target_snowmen if level_info else None
    completed = len(state.get("snowmen", [])) if isinstance(state.get("snowmen"), list) else 0
    if target is None:
        return {
            "status": "unknown",
            "confidence": "none",
            "target_snowmen": None,
            "completed_snowmen": completed,
            "remaining_snowmen": None,
            "reasons": ["The level resource did not expose a target snowman count."],
            "recommended_action": "continue_observing",
        }

    remaining = max(target - completed, 0)
    inventory = snowball_inventory(state, level_info)
    result: dict[str, Any] = {
        "status": "ok",
        "confidence": "none",
        "target_snowmen": target,
        "completed_snowmen": completed,
        "remaining_snowmen": remaining,
        "inventory": inventory,
        "reasons": [],
        "recommended_action": "continue",
        "note": "This is a conservative save-state inference, not a direct read of the transient reset UI bubble.",
    }

    if state.get("current_completed") or remaining == 0:
        result["status"] = "completed"
        return result

    if not inventory.get("reliable"):
        result["status"] = "unknown"
        result["confidence"] = "low"
        result["recommended_action"] = "continue_with_observe"
        result["reasons"] = [inventory.get("note")]
        return result

    counts = inventory.get("counts", {})
    small = int(counts.get("small", 0))
    medium = int(counts.get("medium", 0))
    large = int(counts.get("large", 0))
    total = small + medium + large
    reasons: list[str] = []

    if total < remaining * 3:
        reasons.append(f"need {remaining * 3} snowball units for {remaining} remaining snowman, but only {total} are known")
    if small < remaining:
        reasons.append(
            f"need {remaining} small/head snowball for {remaining} remaining snowman, but only {small} are known"
        )
    if small + medium < remaining * 2:
        reasons.append(
            f"need {remaining * 2} small-or-medium units for heads and middles, but only {small + medium} are known"
        )

    if reasons:
        result["status"] = "likely_unwinnable"
        result["confidence"] = "high"
        result["recommended_action"] = "undo_or_reset"
        result["reasons"] = reasons + ["snowballs can grow or stack, but they cannot shrink back to a smaller size"]
    return result


def level_exits(
    level_info: LevelInfo | None,
    layout_coord: Coord | None,
    layout_objects: tuple[dict[str, Any], ...],
    *,
    completed: bool,
) -> list[dict[str, Any]]:
    if level_info is None or layout_coord is None or not level_info.grid:
        return []

    height = len(level_info.grid)
    result: list[dict[str, Any]] = []
    origin_x, origin_y = layout_coord
    for item in layout_objects:
        kind = item.get("kind")
        if not isinstance(kind, str) or not kind.startswith("entrance_"):
            continue
        global_x = item.get("x")
        global_y = item.get("y")
        if not isinstance(global_x, int) or not isinstance(global_y, int):
            continue

        local_x = global_x - origin_x
        local_y = global_y - origin_y
        if not (0 <= local_y < height):
            continue
        row_width = len(level_info.grid[local_y])
        if not (0 <= local_x < row_width):
            continue

        direction: str | None = None
        side: str | None = None
        stand: Coord | None = None
        if local_y == 0 and height > 1:
            direction = "up"
            side = "top"
            stand = (local_x, 1)
        elif local_y == height - 1 and height > 1:
            direction = "down"
            side = "bottom"
            stand = (local_x, height - 2)
        elif local_x == 0 and row_width > 1:
            direction = "left"
            side = "left"
            stand = (1, local_y)
        elif local_x == row_width - 1 and row_width > 1:
            direction = "right"
            side = "right"
            stand = (row_width - 2, local_y)
        if direction is None or side is None or stand is None:
            continue

        result.append(
            {
                "kind": kind,
                "status": "open" if completed else "closed_until_completion",
                "x": local_x,
                "y": local_y,
                "global_x": global_x,
                "global_y": global_y,
                "side": side,
                "move": direction,
                "stand": [stand[0], stand[1]],
                "note": (
                    "When open, stand on the stand coordinate and press move to leave this level. "
                    "The static grid may still show # at the edge entrance."
                ),
            }
        )
    return result


def state_notes() -> list[str]:
    return [
        "Coordinates are zero-based x,y. x increases to the right; y increases downward.",
        "To push an object in a direction, stand on the opposite side and press toward it. After a successful push, the player occupies the object's previous cell.",
        "A push is blocked when the target's destination cell is a wall, map edge, occupied by an incompatible object, or inaccessible for the needed standing position.",
        "Smaller snowballs can stack onto larger snowballs. Same-size or larger-into-smaller pushes usually behave as blocking or pushing, not completion.",
        "Pushing a stack can detach only the top snowball while the lower part stays put; in that case the player may stay in place.",
        "Use undo/z to back out one bad move. Use reset/r to restart the current level. reset_spawn is where the player appears after reset, not a floor tile trigger.",
        "initial_balls and initial_player come from static level resources; they are not live positions after play begins.",
        "initial_balls.marker is a resource marker, not a numeric size. Use label and stack_bottom_to_top for known markers.",
        "If a live object or player overlaps a static marker cell, the overlay hides the marker there. Check static_marker_overlaps before inferring that the marker vanished.",
        "Level 0 (Lucy) starts with marker 3: a medium snowball with a small snowball stacked on top.",
        "After pushing a marker 3 stack, seeing a live small object plus a small_on_medium grass view is expected stack transition state, not a medium ball shrinking.",
        "Bumping walls, completed snowmen, or other immovable objects can enter a transient push/hug state. This is not stored in progress.json.",
        "After a transient push/hug interaction, the next direction key may only release that pose instead of moving the player.",
        "entities are the saved live objects. The player and moved balls appear there; unchanged initial balls may be absent until touched.",
        "grass entities record consumed snow/roll history. They are useful context but are not movable objects.",
        "grid digits are static initial ball markers. Treat them as a level reference, not as proof of current live occupancy after any move.",
        "level_exits are parsed from layout.txt entrances. After current_completed=true, status=open means stand at stand=x,y and press move to leave; the static grid may still show # there.",
        "dead_state is a conservative save-state inference. The save file exposes tutorial prompt history such as hasBeenPromptedToReset, not the current transient reset UI bubble.",
    ]


def agent_guidance(state: dict[str, Any] | None = None) -> list[str]:
    guidance = [
        "Do not stop after reading state when the current level is incomplete.",
        "Choose a small candidate move batch and run: python3 scripts/snowman_send_keys.py '<moves>' --observe",
        "Use one to five moves per observed batch while learning mechanics; increase --observe-timeout for pushes or animations.",
        "Use map_overlay to check walls and push sides; pushing right requires standing immediately left of the object.",
        "Before pushing, check both the target cell and the destination cell beyond it; walls and occupied cells commonly block pushes.",
        "Use undo/z immediately after a bad push. Use reset/r when several moves have made the state hard to recover.",
        "Do not walk to reset_spawn expecting a reset; reset/r is a command key, not a board tile.",
        "If the last key bumped a wall or completed snowman, budget one direction key for releasing the transient push/hug pose.",
        "This harness intentionally provides no solution route or solver output.",
    ]
    if state is not None and state.get("current_completed"):
        open_exits = [
            item for item in state.get("level_exits", []) if isinstance(item, dict) and item.get("status") == "open"
        ]
        if open_exits:
            first = open_exits[0]
            guidance[0] = (
                "The current saved level is completed; open exit "
                f"{first.get('move')} at {first.get('x')},{first.get('y')}. "
                f"Stand at {coord_text(first.get('stand'))} and press {first.get('move')} to leave."
            )
        else:
            guidance[0] = "The current saved level is completed; continue by navigating in-game with observed movement."
    elif state is not None:
        dead = state.get("dead_state", {})
        if isinstance(dead, dict) and dead.get("status") == "likely_unwinnable":
            reasons = dead.get("reasons", [])
            reason = reasons[0] if isinstance(reasons, list) and reasons else "the known snowball inventory cannot satisfy the remaining snowman goal"
            guidance[0] = f"This saved state appears likely unwinnable: {reason}. Use undo/z if this was caused by the last move, otherwise use reset/r."
    return guidance


def build_state(args: argparse.Namespace) -> dict[str, Any]:
    progress = load_progress(args.progress)
    levels = parse_levels(args.resources / "levels.txt")
    layout = parse_layout(args.resources / "layout.txt")

    level_index = args.level if args.level is not None else int(progress.get("level", -1))
    level_entry = progress.get("levels", {}).get(str(level_index), {})
    level_info = levels[level_index] if 0 <= level_index < len(levels) else None
    layout_coord = layout.positions.get(level_index)

    player = entity_coord(level_entry.get("entities", {}).get("1"))
    reset_spawn = entity_coord({"x": level_entry.get("resetX"), "y": level_entry.get("resetY")})
    current_completed = bool(level_entry.get("completed"))
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
        "layout_coord": coord_list(layout_coord),
        "player": coord_list(player),
        "reset_spawn": coord_list(reset_spawn),
        "current_completed": current_completed,
        "completed_count": len(completed_levels),
        "completed_levels": completed_levels,
        "snowmen": level_entry.get("snowmen", []),
        "current_objects": current_objects(entities),
        "entities": entities,
        "initial_player": coord_list(level_info.initial_player) if level_info else None,
        "initial_balls": list(level_info.initial_balls) if level_info else [],
        "target_snowmen": level_info.target_snowmen if level_info else None,
        "level_exits": level_exits(level_info, layout_coord, layout.objects, completed=current_completed),
        "prompt_history": {
            "hasBeenPromptedToUndo": bool(progress.get("hasBeenPromptedToUndo")),
            "hasBeenPromptedToReset": bool(progress.get("hasBeenPromptedToReset")),
            "hasBeenPromptedToSwipeStack": bool(progress.get("hasBeenPromptedToSwipeStack")),
            "hasBeenPromptedToSwipeMultiple": bool(progress.get("hasBeenPromptedToSwipeMultiple")),
        },
        "state_notes": state_notes(),
    }
    state["static_marker_overlaps"] = static_marker_overlaps(state)
    state["dead_state"] = dead_state(state, level_info)
    state["agent_guidance"] = agent_guidance(state)
    if not args.no_grid:
        state["grid"] = list(level_info.grid) if level_info else []
        state["map_overlay"] = render_map_overlay(state)
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


def coord_tuple(value: Any) -> Coord | None:
    if isinstance(value, list) and len(value) == 2 and all(isinstance(item, int) for item in value):
        return (value[0], value[1])
    return None


def overlay_char(rows: list[list[str]], coord: Coord | None, char: str) -> None:
    if coord is None:
        return
    x, y = coord
    if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
        rows[y][x] = char


def object_symbol(entity_type: Any) -> str:
    if not isinstance(entity_type, str) or not entity_type:
        return "?"
    return LIVE_OBJECT_SYMBOLS.get(entity_type, entity_type[0].lower())


def render_map_overlay(state: dict[str, Any]) -> list[str]:
    grid = state.get("grid", [])
    if not isinstance(grid, list) or not grid:
        return []

    rows = [list(str(row)) for row in grid]
    for row in rows:
        for index, char in enumerate(row):
            if char in "pPq":
                row[index] = "'"

    for item in state.get("snowmen", []):
        if isinstance(item, dict):
            overlay_char(rows, coord_tuple([item.get("x"), item.get("y")]), "N")

    for item in state.get("current_objects", []):
        if isinstance(item, dict):
            overlay_char(rows, coord_tuple([item.get("x"), item.get("y")]), object_symbol(item.get("type")))

    for item in state.get("level_exits", []):
        if isinstance(item, dict) and item.get("status") == "open":
            overlay_char(rows, coord_tuple([item.get("x"), item.get("y")]), "E")

    overlay_char(rows, coord_tuple(state.get("player")), "P")
    return ["".join(row) for row in rows]


def static_marker_overlaps(state: dict[str, Any]) -> list[dict[str, Any]]:
    markers: dict[Coord, dict[str, Any]] = {}
    for item in state.get("initial_balls", []):
        if isinstance(item, dict):
            coord = coord_tuple([item.get("x"), item.get("y")])
            if coord is not None:
                markers[coord] = item

    overlaps: list[dict[str, Any]] = []
    player = coord_tuple(state.get("player"))
    if player in markers:
        marker = markers[player]
        overlaps.append(
            {
                "kind": "player_on_static_marker_cell",
                "x": player[0],
                "y": player[1],
                "marker": marker.get("marker"),
                "label": marker.get("label"),
                "note": "The player is on a static marker reference cell; this marker is stale/reference context, not an extra live blocker.",
            }
        )

    for item in state.get("current_objects", []):
        if not isinstance(item, dict):
            continue
        coord = coord_tuple([item.get("x"), item.get("y")])
        if coord not in markers:
            continue
        marker = markers[coord]
        overlaps.append(
            {
                "kind": "live_object_on_static_marker_cell",
                "x": coord[0],
                "y": coord[1],
                "object_id": item.get("id"),
                "object_type": item.get("type"),
                "marker": marker.get("marker"),
                "label": marker.get("label"),
                "note": "A live object overlaps a static marker reference. Treat this as stack/contact/reference ambiguity, not proof that the static object vanished.",
            }
        )
    return overlaps


def print_text(state: dict[str, Any]) -> None:
    print(f"level={state['level']}")
    print(f"level_name={state['level_name'] or 'unknown'}")
    print(f"layout_coord={coord_text(state['layout_coord'])}")
    print(f"player={coord_text(state['player'])}")
    print(f"reset_spawn={coord_text(state['reset_spawn'])}")
    print(f"current_completed={state['current_completed']}")
    print(f"target_snowmen={state['target_snowmen']}")
    print(f"completed_count={state['completed_count']}")
    print("completed_levels=" + ",".join(map(str, state["completed_levels"])))
    print("snowmen=" + json.dumps(state["snowmen"], ensure_ascii=False, separators=(",", ":")))

    if state.get("dead_state"):
        dead = state["dead_state"]
        print("dead_state:")
        print(
            "  "
            f"status={dead.get('status')} "
            f"confidence={dead.get('confidence')} "
            f"remaining={dead.get('remaining_snowmen')} "
            f"action={dead.get('recommended_action')}"
        )
        inventory = dead.get("inventory", {})
        if isinstance(inventory, dict):
            print(
                "  "
                f"inventory={json.dumps(inventory.get('counts', {}), ensure_ascii=False, separators=(',', ':'))} "
                f"source={inventory.get('source')} "
                f"reliable={inventory.get('reliable')}"
            )
        for reason in dead.get("reasons", []):
            print(f"  reason: {reason}")

    if state.get("level_exits"):
        print("level_exits:")
        for item in state["level_exits"]:
            print(
                "  "
                f"{item.get('status')} "
                f"{item.get('move')} "
                f"at {item.get('x')},{item.get('y')} "
                f"stand={coord_text(item.get('stand'))} "
                f"kind={item.get('kind')}"
            )

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

    if state.get("static_marker_overlaps"):
        print("static_marker_overlaps:")
        for item in state["static_marker_overlaps"]:
            print(
                "  "
                f"{item.get('kind')} "
                f"at {item.get('x')},{item.get('y')} "
                f"marker={item.get('marker')} "
                f"label={item.get('label')} "
                f"object={item.get('object_type', 'none')} "
                f"id={item.get('object_id', 'none')}"
            )
            print(f"    note: {item.get('note')}")

    if "grid" in state:
        print("grid:")
        for row in state["grid"]:
            print(f"  {row}")
    if state.get("map_overlay"):
        print("map_overlay:")
        print(
            "  legend: P player; s/m/l live balls; N completed snowman; E open level exit; "
            "1-5 static markers; # wall; x static outside/exit marker; overlay priority P > E > live > static"
        )
        width = max(len(row) for row in state["map_overlay"])
        print("  x " + "".join(str(index % 10) for index in range(width)))
        for y, row in enumerate(state["map_overlay"]):
            print(f"  y{y} {row}")


def compact_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": state.get("timestamp"),
        "level": state.get("level"),
        "level_name": state.get("level_name"),
        "player": state.get("player"),
        "reset_spawn": state.get("reset_spawn"),
        "current_completed": state.get("current_completed"),
        "target_snowmen": state.get("target_snowmen"),
        "completed_count": state.get("completed_count"),
        "dead_state": state.get("dead_state", {}),
        "level_exits": state.get("level_exits", []),
        "current_objects": state.get("current_objects", []),
        "snowmen": state.get("snowmen", []),
        "initial_player": state.get("initial_player"),
        "initial_balls": state.get("initial_balls", []),
        "static_marker_overlaps": state.get("static_marker_overlaps", []),
        "map_overlay": state.get("map_overlay", []),
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
        f"player={coord_text(state.get('player'))} reset_spawn={coord_text(state.get('reset_spawn'))}",
    ]

    dead = state.get("dead_state", {})
    if isinstance(dead, dict) and dead.get("status") != "completed":
        lines.append(
            "dead_state: "
            f"status={dead.get('status')} "
            f"confidence={dead.get('confidence')} "
            f"remaining={dead.get('remaining_snowmen')} "
            f"action={dead.get('recommended_action')}"
        )
        inventory = dead.get("inventory", {})
        if isinstance(inventory, dict):
            lines.append(
                "  "
                f"inventory={json.dumps(inventory.get('counts', {}), ensure_ascii=False, separators=(',', ':'))} "
                f"source={inventory.get('source')} "
                f"reliable={inventory.get('reliable')}"
            )
        if dead.get("status") == "likely_unwinnable":
            for reason in dead.get("reasons", []):
                lines.append(f"  reason: {reason}")

    map_overlay = state.get("map_overlay", [])
    if map_overlay:
        lines.append("map_overlay:")
        lines.append(
            "  legend: P player; s/m/l live balls; N completed snowman; E open level exit; "
            "1-5 static markers; # wall; x static outside/exit marker; overlay priority P > E > live > static"
        )
        width = max(len(row) for row in map_overlay)
        lines.append("  x " + "".join(str(index % 10) for index in range(width)))
        for y, row in enumerate(map_overlay):
            lines.append(f"  y{y} {row}")

    exits = state.get("level_exits", [])
    if exits:
        lines.append("level_exits:")
        for item in exits:
            lines.append(
                "  "
                f"{item.get('status')} "
                f"{item.get('move')} "
                f"at {item.get('x')},{item.get('y')} "
                f"stand={coord_text(item.get('stand'))} "
                f"kind={item.get('kind')}"
            )

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

    overlaps = state.get("static_marker_overlaps", [])
    if overlaps:
        lines.append("static_marker_overlaps:")
        for item in overlaps:
            lines.append(
                "  "
                f"{item.get('kind')} "
                f"at {item.get('x')},{item.get('y')} "
                f"marker={item.get('marker')} "
                f"label={item.get('label')} "
                f"object={item.get('object_type', 'none')} "
                f"id={item.get('object_id', 'none')}"
            )
            lines.append(f"    note: {item.get('note')}")
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


def level_exit_summary(state: dict[str, Any]) -> str:
    exits = state.get("level_exits", [])
    if not isinstance(exits, list):
        return "none"
    pieces: list[str] = []
    for item in exits:
        if not isinstance(item, dict):
            continue
        pieces.append(
            f"{item.get('status')} {item.get('move')} at {item.get('x')},{item.get('y')} "
            f"stand={coord_text(item.get('stand'))}"
        )
    return "; ".join(pieces) if pieces else "none"


def dead_state_summary(state: dict[str, Any]) -> str:
    dead = state.get("dead_state", {})
    if not isinstance(dead, dict):
        return "none"
    return (
        f"{dead.get('status')} confidence={dead.get('confidence')} "
        f"remaining={dead.get('remaining_snowmen')} action={dead.get('recommended_action')}"
    )


def diff_state_lines(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    metadata_lines: list[str] = []
    material_lines: list[str] = []
    if before.get("timestamp") != after.get("timestamp"):
        metadata_lines.append(f"timestamp: {before.get('timestamp')} -> {after.get('timestamp')}")

    for key in ("level", "level_name", "current_completed"):
        if before.get(key) != after.get(key):
            material_lines.append(f"{key}: {before.get(key)} -> {after.get(key)}")

    if before.get("player") != after.get("player"):
        material_lines.append(f"player: {coord_text(before.get('player'))} -> {coord_text(after.get('player'))}")

    if before.get("snowmen") != after.get("snowmen"):
        material_lines.append(
            "snowmen: "
            + json.dumps(before.get("snowmen", []), ensure_ascii=False, separators=(",", ":"))
            + " -> "
            + json.dumps(after.get("snowmen", []), ensure_ascii=False, separators=(",", ":"))
        )

    if before.get("level_exits") != after.get("level_exits"):
        material_lines.append(f"level_exits: {level_exit_summary(before)} -> {level_exit_summary(after)}")

    if before.get("dead_state") != after.get("dead_state"):
        material_lines.append(f"dead_state: {dead_state_summary(before)} -> {dead_state_summary(after)}")

    before_objects = {object_key(item): item for item in before.get("current_objects", [])}
    after_objects = {object_key(item): item for item in after.get("current_objects", [])}
    for key in sorted(before_objects.keys() - after_objects.keys()):
        item = before_objects[key]
        material_lines.append(f"removed: {item.get('type')} {item.get('x')},{item.get('y')} id={item.get('id')}")
    for key in sorted(after_objects.keys() - before_objects.keys()):
        item = after_objects[key]
        material_lines.append(f"added: {item.get('type')} {item.get('x')},{item.get('y')} id={item.get('id')}")
    for key in sorted(before_objects.keys() & after_objects.keys()):
        old = before_objects[key]
        new = after_objects[key]
        old_pos = (old.get("x"), old.get("y"))
        new_pos = (new.get("x"), new.get("y"))
        if old.get("type") != new.get("type") or old_pos != new_pos:
            material_lines.append(
                f"object {key}: {old.get('type')} {old_pos[0]},{old_pos[1]} "
                f"-> {new.get('type')} {new_pos[0]},{new_pos[1]}"
            )

    if not metadata_lines and not material_lines:
        return [
            "no saved state change",
            "hint: the move may be blocked, may only have changed transient push/hug state, or may need a longer --observe-timeout.",
        ]
    if metadata_lines and not material_lines:
        return metadata_lines + [
            "no material state change",
            "hint: timestamp changed but player, current_objects, snowmen, and completion did not. Treat this as blocked movement, transient push/hug state, or a pose release.",
        ]
    return metadata_lines + material_lines


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
