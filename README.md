<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/86fa31b1-9229-484a-9ce8-6314d4015340" />

# davinci-resolve-cli (`dvr`)

[![PyPI version](https://img.shields.io/pypi/v/davinci-resolve-cli.svg)](https://pypi.org/project/davinci-resolve-cli/)
[![Python versions](https://img.shields.io/pypi/pyversions/davinci-resolve-cli.svg)](https://pypi.org/project/davinci-resolve-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Build](https://github.com/Poechant/davinci-resolve-cli/actions/workflows/build.yml/badge.svg)](https://github.com/Poechant/davinci-resolve-cli/actions/workflows/build.yml)

A CLI for DaVinci Resolve 18+ — project / media / render / timeline control for humans and AI agents.

## Install

```bash
pipx install davinci-resolve-cli
```

Requires DaVinci Resolve 18+ already installed (Studio recommended). macOS first; Windows/Linux follow.

## Quickstart

```bash
# Health check
dvr doctor

# Project ops
dvr project list
dvr project current

# Media batch
dvr media import ~/footage --recursive --bin "Day1"

# Render (async)
JOB=$(dvr render submit --preset "H.264 Master" --timeline cur --output ~/out.mp4 --format json | jq -r .jobId)
dvr render wait "$JOB"

# Timeline scripted edits
dvr timeline marker add --at 01:00:05:00 --note "review"
```

## Capabilities at a glance

| Domain | Subcommands | What it does |
|--------|-------------|--------------|
| `doctor` | — | Diagnose the Resolve bridge environment (version, Studio / Free, API path, issues) |
| `project` | `list / current / open / new / close / save / export / import` | Project library CRUD |
| `media` | `import / list / tag` | Media-pool batch ops — recursive import, per-bin lookup, 16 named flag colors, partial-failure reporting |
| `render` | `presets / submit / status / list / wait / cancel` | Async render queue. `submit` returns a `jobId` immediately; `wait` blocks until terminal (`completed` / `failed` / `cancelled`) |
| `timeline` | `list / current / open / new / delete / clips / cut / move`<br>`marker add / delete / list` | Timeline CRUD + marker ops + WI-bridged razor cut and clip move |
| `mcp` | — | Start a stdio MCP server exposing 20 tools (one per CLI verb), each with a JSON-Schema'd `inputSchema` |
| `install-wi` | `--uninstall / --force` | Deploy / remove the Workflow Integration plugin used by `timeline cut` and `timeline move` |

Conventions across every command:

- `--format json|yaml|table` — JSON by default in non-TTY, `table` (rich) in TTY, override via `DVR_OUTPUT`
- Structured errors on stderr — `{"errorCode", "message", "hint"}`, stable codes (`resolve_not_running`, `validation_error`, `not_found`, `api_call_failed`, `wi_unavailable`, …)
- `--dry-run` on every mutating command — prints the `planned` actions without touching Resolve
- Exit codes: `0` ok, `1` user error, `2` Resolve unavailable, `3` API call failed

## Output formats

| context | default |
|---------|---------|
| TTY     | `table` (rich) |
| pipe / non-TTY | `json` |

Override with `--format json|yaml|table` or `DVR_OUTPUT=yaml`.

## AI Agent

`dvr` ships **two** complementary AI-agent integration paths.

### 1. Skill file (`SKILL.md`)

A SKILL.md packaged with the wheel; auto-discovered by skill systems that scan installed packages. Five worked example prompts:

- "Render the current timeline as 1080p mp4"
- "List clips imported today and tag them green"
- "Wait for render job X and tell me when it finishes"
- "Check if Resolve is ready"
- "Tag all clips in Day1 bin as Green for review"

### 2. MCP server (`dvr mcp`)

Standard stdio MCP server exposing 20 tools across `doctor` / `project.*` / `media.*` / `render.*` / `timeline.*` namespaces. Any MCP-aware AI client can wire it up:

```jsonc
// .mcp.json or your client's MCP server config
{
  "mcpServers": {
    "davinci-resolve": {
      "command": "dvr",
      "args": ["mcp"]
    }
  }
}
```

Tool errors are returned as structured JSON `{"errorCode", "message", "hint"}` matching the CLI's stderr contract — same error codes (`resolve_not_running`, `validation_error`, `not_found`, etc.) so an agent can branch on them deterministically.

Verify the server is reachable:

```bash
dvr mcp   # blocks, reads stdin/writes stdout per MCP spec
```

## Compatibility

| OS | Status |
|----|--------|
| macOS (Apple Silicon / Intel) | ✅ primary, end-to-end verified |
| Windows | ✅ unit + CI tested (real-Resolve smoke pending community feedback) |
| Linux | ✅ unit + CI tested (Resolve Studio Linux only) |

| Resolve | Status |
|---------|--------|
| 18.x Studio | ✅ |
| 18.x Free   | ⚠️ partial (render encoders limited) |
| 17.x or older | ❌ unsupported |

## Cookbook

Five end-to-end recipes covering the most common workflows. Each is a copy-paste shell snippet that assumes DaVinci Resolve 18+ Studio is running and a project is open.

### 1. Render the current timeline as 1080p H.264 mp4

```bash
# Preflight: make sure the bridge is healthy
dvr doctor --format json | jq -e '.bridgeStatus == "ok"' >/dev/null || { echo "Resolve not ready"; exit 2; }

# Pick the first preset whose name contains "H.264"
PRESET=$(dvr render presets --format json | jq -r '.[] | select(test("H\\.264"; "i"))' | head -1)

# Submit (async — returns immediately), then block until done
JOB=$(dvr render submit --preset "$PRESET" --timeline cur --output ~/Renders/out.mp4 --start --format json | jq -r .jobId)
dvr render wait "$JOB"   # progress to stderr, terminal status to stdout
```

### 2. Import a SD card's footage into per-date bins

```bash
# Assumes ~/footage/<YYYY-MM-DD>/ structure
for day_dir in ~/footage/*/; do
  day=$(basename "$day_dir")
  dvr media import "$day_dir" --bin "$day" --recursive --format json | jq '.imported | length' \
    | xargs -I{} echo "imported {} clips into '$day'"
done
```

### 3. Tag every clip in a bin as "Green" for review (skipping ones already tagged)

```bash
BIN="Day1"
IDS=$(dvr media list --bin "$BIN" --format json \
  | jq -r '.[] | select(.flags | index("Green") | not) | .id')
[ -n "$IDS" ] && dvr media tag $IDS --color Green --format json
```

### 4. Drop chapter markers from a CSV file (timecode, label)

```bash
# chapters.csv:
#   00:00:00:00,intro
#   00:01:30:00,demo
#   00:04:15:00,outro
while IFS=, read -r tc label; do
  dvr timeline marker add --at "$tc" --name "$label" --color Sky --format json >/dev/null
done < chapters.csv

dvr timeline marker list --format json | jq '.[] | "\(.timecode) → \(.name)"'
```

### 5. AI agent: render via MCP server

Wire `dvr mcp` into any MCP-aware client (most desktop AI assistants now support MCP — check your client's docs for the right config file path):

```jsonc
// ~/.config/<client>/mcp.json
{ "mcpServers": { "davinci-resolve": { "command": "dvr", "args": ["mcp"] } } }
```

Then ask the agent:

> "Render the currently open timeline as 1080p H.264, save it to ~/out.mp4, and tell me when it's done."

The agent will call `doctor` → `render.presets` → `render.submit(start=true)` → `render.wait` automatically. Tool errors come back as structured `{errorCode, message, hint}` so the agent can branch on `resolve_not_running` / `validation_error` / etc. deterministically.

## Development

```bash
pip install -e ".[dev]"
pytest                              # unit only
pytest -m integration               # requires Resolve running
```

## License

MIT
