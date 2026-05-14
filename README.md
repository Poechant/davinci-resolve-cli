# davinci-resolve-cli (`dvr`)

A CLI for DaVinci Resolve 18+ — project / media / render / timeline control for humans and AI agents.

> Status: **alpha (v0.1 in development)** — see `versions/v0.1/milestones/M1-*.md` for scope.

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

## Output formats

| context | default |
|---------|---------|
| TTY     | `table` (rich) |
| pipe / non-TTY | `json` |

Override with `--format json|yaml|table` or `DVR_OUTPUT=yaml`.

## AI Agent

This package ships a `SKILL.md` with five worked examples for AI agent skill systems. Example prompts:

- "Render the current timeline as 1080p mp4"
- "List clips imported today and tag them green"
- "Wait for render job X and tell me when it finishes"

## Compatibility

| OS | Status |
|----|--------|
| macOS (Apple Silicon / Intel) | ✅ primary |
| Windows | 🚧 planned v0.2 |
| Linux | 🚧 planned v0.2 |

| Resolve | Status |
|---------|--------|
| 18.x Studio | ✅ |
| 18.x Free   | ⚠️ partial (render encoders limited) |
| 17.x or older | ❌ unsupported |

## Development

```bash
pip install -e ".[dev]"
pytest                              # unit only
pytest -m integration               # requires Resolve running
```

## License

MIT
