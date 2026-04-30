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

Send movement keys:

```bash
python3 scripts/snowman_send_keys.py 'left,up*2,right'
```

Preview parsed input without sending keys:

```bash
python3 scripts/snowman_send_keys.py 'left,up*2,right' --dry-run
```

Supported move names include `left`, `right`, `up`, `down`, `undo`/`z`,
`reset`/`r`, `confirm`/`space`, `enter`, and `escape`.

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
