---
name: davinci-resolve-cli
description: |
  Use this skill when the user wants to script DaVinci Resolve from the command
  line — list/open/save projects, batch-import media, queue or wait on render
  jobs, list timelines/clips, or add/delete timeline markers. Trigger on
  mentions of DaVinci Resolve, "render this timeline", "import this footage",
  "tag clips", or any DaVinci-related automation. Requires DaVinci Resolve 18+
  Studio running on the same machine.
binary: dvr
output: json
---

# davinci-resolve-cli (`dvr`) — Skill

`dvr` is a CLI for DaVinci Resolve 18+. It bridges into a running Resolve via
DaVinciResolveScript and exposes a structured, JSON-by-default command surface
optimized for AI agents. Always pass `--format json` when invoking from a
non-TTY context so the output is parseable.

## Preflight

Before any action, verify the bridge is healthy:

```bash
dvr doctor --format json
```

Expected: `bridgeStatus == "ok"`. If not, surface the `issues[]` array to the
user and stop — Resolve must be launched manually.

## Command Map

| Domain    | Commands                                                                 |
|-----------|--------------------------------------------------------------------------|
| Environment | `dvr doctor`                                                           |
| Project   | `project list / open / new / close / save / export / import / current`   |
| Media     | `media import / list / tag`                                              |
| Render    | `render presets / submit / status / list / wait / cancel`                |
| Timeline  | `timeline list / current / open / new / clips / marker add/delete/list` |

All commands accept `--format json|yaml|table` (default: JSON for non-TTY).
All mutating timeline commands accept `--dry-run`.

## Error Contract

Errors are emitted to stderr as JSON `{"errorCode": "...", "message": "...", "hint": "..."}`.
Exit code 0 = success, 1 = user error, 2 = Resolve not reachable, 3 = Resolve API failure.

Common `errorCode` values: `resolve_not_running`, `version_unsupported`,
`api_unavailable`, `validation_error`, `not_found`, `api_call_failed`.

---

## Example Tasks

### 1. Render the current timeline as 1080p H.264

```bash
# Preflight
dvr doctor --format json | jq -e '.bridgeStatus == "ok"' >/dev/null

# Pick a preset and submit (async — returns immediately)
PRESET=$(dvr render presets --format json | jq -r '.[] | select(test("H\\.264"; "i"))' | head -1)
SUBMIT=$(dvr render submit \
  --preset "$PRESET" \
  --timeline cur \
  --output ~/Renders/out.mp4 \
  --start \
  --format json)
JOB=$(echo "$SUBMIT" | jq -r .jobId)

# Block until done; progress is on stderr (safe to ignore from agents)
dvr render wait "$JOB" --format json
```

### 2. List media imported into the current bin

```bash
dvr media list --format json | jq '.[] | {id, name, resolution, duration}'
```

To filter by a specific bin:

```bash
dvr media list --bin "Day1" --format json
```

### 3. Batch tag clips in a bin as "Green" for review

```bash
# Collect all clip IDs in Day1 (excludes those already Green)
IDS=$(dvr media list --bin "Day1" --format json \
  | jq -r '.[] | select(.flags | index("Green") | not) | .id')

# Tag them (no rollback on partial failure — failed[] is reported)
dvr media tag $IDS --color Green --format json
```

### 4. Wait on a known job and report when it finishes

```bash
JOB="$1"  # jobId given by the user
RESULT=$(dvr render wait "$JOB" --interval 2 --format json)
STATUS=$(echo "$RESULT" | jq -r .status)
case "$STATUS" in
  completed) echo "Render $JOB finished successfully." ;;
  failed)    echo "Render $JOB failed."; exit 1 ;;
  cancelled) echo "Render $JOB was cancelled." ;;
esac
```

### 5. Check Resolve is ready before doing anything else

```bash
REPORT=$(dvr doctor --format json)
if [ "$(echo "$REPORT" | jq -r .bridgeStatus)" != "ok" ]; then
  echo "$REPORT" | jq '.issues[]'
  echo "Resolve is not ready. Ask the user to launch DaVinci Resolve 18+." >&2
  exit 2
fi
echo "$REPORT" | jq '{version, edition, platform}'
```

---

## Behavioral Hints for Agents

- **Long-running commands**: only `render wait` blocks. Everything else returns
  in milliseconds. Prefer `submit` + later `wait` over running things
  synchronously, especially when chaining steps.
- **Dry-run**: when a user proposes a destructive timeline edit, run
  `dvr timeline marker add --dry-run ...` first and present the `planned[]`
  array before executing.
- **Timecode**: timecode strings are non-drop, `HH:MM:SS:FF`. The CLI rejects
  drop-frame syntax (`HH:MM:SS;FF`) is normalized for now but treated as ND.
- **Bin paths**: bin selectors are case-sensitive folder names directly under
  the master bin. `Master`, `/`, and `root` all alias to the root.
- **Idempotency**: `marker add` returns `api_call_failed` if a marker already
  exists at the same frame — there is no "upsert" mode. Delete first if you
  want to replace.
- **State preservation**: `media import --bin X` temporarily switches the
  current bin to `X` for the import and then restores it.
