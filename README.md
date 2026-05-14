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

## Development

```bash
pip install -e ".[dev]"
pytest                              # unit only
pytest -m integration               # requires Resolve running
```

## License

MIT
