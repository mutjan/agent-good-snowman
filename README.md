# A Good Snowman Agent Harness

Minimal macOS tooling for agent experiments with **A Good Snowman Is Hard To
Build**.

This repository is meant to test an agent's own puzzle-solving ability. It
therefore only exposes two primitives:

- read the current game/save state;
- send real keyboard input to the running game.

## Requirements

- macOS.
- A local install of A Good Snowman Is Hard To Build.
- Python 3.
- Xcode Command Line Tools for `clang`.
- macOS Accessibility permission for the app running these scripts, such as
  Terminal or Codex.

The game should be running before sending keys. The first input command may
trigger macOS Automation or Accessibility prompts.

## Setup

Create a local config:

```bash
python3 scripts/snowman_config.py --create
```

This writes `snowman_config.json`, which is ignored by git. Inspect it and make
sure the paths match your machine:

```bash
python3 scripts/snowman_config.py
```

Expected fields include:

```text
game_files_found=True
save_file_found=True
```

You can also use a custom config path with `SNOWMAN_CONFIG=/path/to/config.json`
or `--config /path/to/config.json`.

## Commands

Read current state:

```bash
python3 scripts/snowman_read_state.py
```

Read machine-readable state:

```bash
python3 scripts/snowman_read_state.py --json
```

Read a concise state summary:

```bash
python3 scripts/snowman_read_state.py --compact --explain
```

The state output includes agent-facing notes. In particular, `current_objects`
contains saved live entities, while `initial_balls` is static level reference
data. Static entries use `marker`, `label`, and `stack_bottom_to_top`; the
marker is not a numeric snowball size. For example, level 0 (`Lucy`) starts with
marker `3`, meaning a small snowball stacked on a medium snowball. After reading
an incomplete level, continue with a small observed action batch instead of
stopping at inspection. If a pushed stack later appears as a live `small` object
plus a `small_on_medium...` grass view, treat that as stack transition state.
Interactions with walls, completed snowmen, and other immovable objects can also
put the player in a transient push/hug pose that is not stored in `progress.json`;
the next direction key may only release that pose.
Concise output also includes `map_overlay`, where `P` is the player, `s/m/l`
are live snowballs, `N` is a completed snowman, `E` is an open level exit,
digits are static markers, and `#` is wall. Coordinates are `x,y`, with `x`
increasing rightward and `y` increasing downward. The overlay priority is
player, then open exits, then live objects, then static markers. If a live
object or the player overlaps a static marker cell, read
`static_marker_overlaps` before inferring that the marker has vanished.

After `current_completed=true`, `level_exits` lists open exits parsed from
`layout.txt`. Use its `stand=x,y` and `move=direction` values to leave the
current level. The static grid may still show `#` at the edge entrance; trust
`level_exits` over the raw static wall character.

The state output also includes `dead_state`, a conservative inference from the
saved target count and known snowball sizes. If it reports
`status=likely_unwinnable`, the current saved state probably cannot finish the
remaining snowman because at least one required size is no longer available.
Prefer `undo`/`z` if the last move caused it, otherwise use `reset`/`r`. This is
not a direct read of the transient in-game reset bubble; save fields such as
`hasBeenPromptedToReset` only record tutorial prompt history.

Send movement keys:

```bash
python3 scripts/snowman_send_keys.py 'left,up*2,right'
```

Send movement keys and show the saved-state change after each key:

```bash
python3 scripts/snowman_send_keys.py 'left,up*2,right' --observe
```

When observing pushes or animations, the script polls the save file briefly so
slow state updates are less likely to be reported as no-ops. Use
`--observe-timeout` or `--observe-poll` to tune this. A no-op after bumping a
wall or hugging a completed snowman may still be a transient interaction state
rather than a failed keypress.
If only the save timestamp changes, `--observe` reports `no material state
change`; do not treat that as successful movement or object motion.

Preview parsed input without sending keys:

```bash
python3 scripts/snowman_send_keys.py 'left,up*2,right' --dry-run
```

Supported move names include `left`, `right`, `up`, `down`, `undo`/`z`,
`reset`/`r`, `confirm`/`space`, `enter`, and `escape`.

`undo`/`z` is the normal one-step backtrack. `reset`/`r` restarts the current
level. The `reset_spawn=x,y` value in state output is where the player appears
after reset, not a board tile that triggers reset when walked onto.

Before pushing, check the target cell and the cell beyond it. Walls, map edges,
incompatible occupied cells, or an inaccessible standing position block pushes.
Pushing a stack can detach only the top snowball while the lower part stays put;
trust the observed diff over assumptions.

The default input method targets the `Snowman` process through System Events.
Alternative methods are available with `--method cgevent` and
`--method applescript`.

## Files

- `scripts/snowman_config.py`: shared local configuration and path checks.
- `scripts/snowman_read_state.py`: read-only reporter for `progress.json`,
  `levels.txt`, and `layout.txt`.
- `scripts/snowman_send_keys.py`: compact move parser and keyboard sender.
- `scripts/snowman_cgevent_keys.c`: tiny CGEvent helper compiled on demand by
  `snowman_send_keys.py`.
- `snowman_config.example.json`: portable config template.

## Safety And Scope

- State reading is read-only.
- Actions are sent as normal keyboard input.
- Trying to use process probes can make the game process stop responding.
- Generated binaries, local configs, pycache, and local save artifacts are
  ignored by git.

## Changelog

### 2026-05-01

- Added `map_overlay` to compact state output, including player, live balls,
  completed snowmen, static markers, and open level exits.
- Added static marker explanations so agents distinguish resource markers from
  live snowball sizes.
- Added `static_marker_overlaps` to flag player or live-object overlap with
  stale static marker cells.
- Added `level_exits` from `layout.txt`, with `stand=x,y` and `move=direction`
  guidance after a level is completed.
- Added `dead_state` conservative inference for likely unwinnable save states,
  with `undo`/`reset` recovery guidance.
- Improved `--observe` diffs with `no material state change`, level exit
  changes, and dead-state changes.
- Documented undo/reset commands, push blocking rules, stack splitting, transient
  push/hug poses, and `reset_spawn` semantics.
