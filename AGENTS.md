# AGENTS.md — Working on this codebase with an AI agent

> If you're a human contributor: this file's instructions are also useful for you. If you're an AI agent (Cursor / Codex / Aider / Continue / …) helping a contributor, **read this before touching code**.

## What this project is

`davinci-resolve-cli` (`dvr`) is a Python CLI that bridges DaVinci Resolve 18+ over `DaVinciResolveScript`. End-users (humans + AI agents) drive Resolve through five command domains (`doctor / project / media / render / timeline`), plus a stdio MCP server and a Workflow Integration plugin for ops the Python API does not cover.

The product surface is **stable** as of v0.2.x — every new command should map cleanly onto an existing namespace (`<domain>.<verb>`) and follow the conventions below.

## Repository map

```
src/dvr/
├── cli.py                # Typer root app
├── bootstrap.py          # DVR Script discovery & connection
├── resolve.py            # ResolveClient Protocol + RealResolveClient
├── output.py             # table / json / yaml renderer
├── errors.py             # DvrError + all stable error codes
├── timecode.py           # TC ↔ frame helpers
├── wi_client.py          # WI bridge HTTP server (CLI side)
├── commands/
│   ├── _client.py        # lazy ResolveClient accessor
│   ├── doctor.py / project.py / media.py / render.py / timeline.py
│   ├── mcp_cmd.py / install_wi.py
├── mcp/
│   ├── server.py         # stdio MCP Server
│   └── tools.py          # tool registry: 20 tools
├── jobs/store.py         # ~/.dvr/jobs.json state machine
└── schemas/*.json        # JSON Schemas for every command's output

wi-plugin/                # Resolve Workflow Integration plugin bundle
tests/unit/               # 184+ tests, FakeResolve fixture in conftest.py
SKILL.md                  # end-user AI agent guide (shipped in the wheel)
```

## Hard rules

1. **TDD always.** A new command means: write `tests/unit/test_<cmd>.py` first against the existing `FakeResolve` fixture (`conftest.py`), then the implementation. Failing tests are signal, not friction.
2. **Pure-function business logic in `commands/*.py`** — Typer wrappers are thin IO at the bottom of each file. This split lets tests call helpers directly without invoking Typer.
3. **All errors are `DvrError` subclasses** (`src/dvr/errors.py`). Pick the right code:
   - `resolve_not_running` (2) — bridge can't reach Resolve
   - `version_unsupported` (1) — Resolve < 18
   - `api_unavailable` (2) — DaVinciResolveScript module/lib missing
   - `api_call_failed` (3) — Resolve API returned `False` / `None`
   - `validation_error` (1) — user input invalid
   - `not_found` (1) — referenced entity (clip / job / timeline) doesn't exist
   - `wi_unavailable` (2) — WI plugin not reachable
   - `wi_error` (3) — WI plugin returned an error
   - Never `raise Exception(...)` — pick a code or add a new one.
4. **Mutating commands must support `--dry-run`** — return `{dryRun: True, planned: [{action, …}]}` and skip the Resolve call entirely (verifiable in tests via FakeResolve seeing zero mutating calls).
5. **Schemas first.** Every command output goes through a JSON Schema in `src/dvr/schemas/*.json` and is `jsonschema.validate()`-tested. Add a `$defs` entry for any new return shape.
6. **MCP tool registry follows CLI 1:1.** New CLI command → matching entry in `src/dvr/mcp/tools.py`. Tool names use dot notation: `domain.verb` (use underscore for multi-word verbs, e.g. `timeline.marker_add`).
7. **Cross-platform first.** Tests run on macOS / Windows / Linux in CI. Don't assume `/` separators in fixtures. Don't use `Path(...).is_absolute()` for cross-OS path checks. Test fixtures should pass `default_paths("Windows")` on a macOS host (and vice versa).
8. **No `print()` in production code.** Use `output.emit(data, fmt)` for happy-path output; errors flow through `cli.run()`'s `DvrError` handler and emit structured JSON to stderr automatically.

## Conventions checklist before opening a PR

- [ ] New command has `--format json|yaml|table` (free via Typer flag + `output.resolve_format`)
- [ ] Schema added in `src/dvr/schemas/` + referenced in test
- [ ] MCP tool registered in `src/dvr/mcp/tools.py` with valid `inputSchema`
- [ ] `CHANGELOG.md` entry under an unreleased version bump
- [ ] `pytest -q` is green (locally on macOS / via CI matrix elsewhere)
- [ ] Keep the project **vendor-neutral on AI agents** — refer to "AI agent" / "MCP-aware assistant" generically, do not bake any one AI vendor's product name into source / docs / SKILL.md
- [ ] Wheel rebuild + `twine check dist/*` clean if pyproject changed

## Common tasks

### Adding a new subcommand to an existing domain

```python
# 1. Add a pure helper in src/dvr/commands/<domain>.py
def my_thing(client: ResolveClient, foo: str) -> dict[str, Any]:
    proj = _current_project_or_raise(client)
    # … operate on `proj` via the small set of Fake-mimicked APIs …
    return {"ok": True, …}

# 2. Wrap it in a Typer command at the bottom of the same file
@app.command("my-thing")
def cli_my_thing(foo: str, fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    emit(my_thing(client_mod.get(), foo), resolve_format(fmt))

# 3. Add an MCP tool entry in src/dvr/mcp/tools.py
ToolSpec("domain.my_thing", "Describe it.", _schema({"foo":{"type":"string"}}, ["foo"]), _h_my_thing)

# 4. Write tests/unit/test_<domain>.py covering happy path + every DvrError raise path
```

### Adding a new error code

1. Subclass `DvrError` in `src/dvr/errors.py` with `error_code`, `message`, optional `hint`, `exit_code`.
2. Add the code to `src/dvr/schemas/error.json` `errorCode` enum.
3. Add a parametrized case in `tests/unit/test_errors.py`.

### Versioning

- Patches (`0.2.x`): bug fixes, doc, infra — bump `pyproject.toml` + `src/dvr/__init__.py` + add `CHANGELOG.md` entry, push tag, PyPI auto-publishes via OIDC Trusted Publishing (`.github/workflows/publish.yml`).
- Minors (`0.x.0`): new command domains, MCP transports, anything user-facing — open a context in `flow` first, write a milestone (`davinci-resolve-cli/versions/v0.x/milestones/`), then implement against AC.

## Things to **not** touch without discussion

- `RESOLVE_SCRIPT_API` / `RESOLVE_SCRIPT_LIB` env vars: only ever set inside `bootstrap.inject_sys_path` — don't sprinkle elsewhere.
- The `~/.dvr/jobs.json` schema: add fields, don't rename / remove existing ones.
- `requires-python` floor: was 3.10 from 0.2.1 because `mcp >= 1.0` transitively requires it. Don't lower without a plan for mcp.
- v0.2.0 PyPI: it's yanked; don't try to revive it.

## How to run locally

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q                            # unit, ~2s, no Resolve needed
.venv/bin/pytest -m integration                # requires a running Resolve 18+
.venv/bin/dvr doctor --format json             # smoke against your real Resolve
```

## When in doubt

Look at the closest existing command for prior art. The five domains were designed to be parallel — anything `media.tag` does, `timeline.marker add` does in the same shape, just on a different Resolve entity.
