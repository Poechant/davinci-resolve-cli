# Changelog

All notable changes to this project will be documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.2.3] - 2026-05-16

### Added
- **README "Capabilities at a glance" table** — single reference matrix of all
  seven command domains, every subcommand, and the cross-cutting conventions
  (`--format`, structured errors, `--dry-run`, exit codes). Sits between
  Quickstart and Output formats so new visitors can judge fit in 5 seconds
  without scrolling through the Cookbook.

No code or behavior changes; doc-only patch.

## [0.2.2] - 2026-05-16

### Added
- **`dvr timeline delete <name>`** — delete a timeline by name. Supports `--dry-run`.
  Auto-promotes another timeline to "current" if the deleted one was active.
- **README Cookbook** — five copy-paste end-to-end recipes covering render,
  batch import per date, bulk tag, CSV-driven markers, and MCP-agent dispatch.

### Tests
- 6 new unit tests covering `timeline delete` happy path, missing name, empty
  name, dry-run, current-timeline promotion, and last-timeline removal.
- 184 unit tests total (was 178).

## [0.2.1] - 2026-05-16

### Fixed
- **Drop Python 3.9 support.** The `mcp` runtime dependency (introduced for the
  `dvr mcp` server in v0.2.0) requires Python 3.10+, so `pipx install` on a 3.9
  interpreter failed with `No matching distribution found for mcp>=1.0`.
  `requires-python` is now `>=3.10`; classifiers, ruff target, and the CI
  matrix have been aligned. v0.2.0 has been yanked from PyPI.
- Cross-platform test fixtures: `FakeMediaPool.ImportMedia` /
  `FakeProjectManager.ImportProject` and `tests/unit/test_bootstrap_cross_platform.py`
  no longer assume POSIX path separators, fixing 5 spurious Windows-only CI
  failures. Production code unchanged.

## [0.2.0] - 2026-05-15 (yanked — install with Python 3.10+)

### Added
- **PyPI distribution** — `pipx install davinci-resolve-cli` now works directly from PyPI; OIDC Trusted Publishing via GitHub Actions (`.github/workflows/publish.yml`).
- **Cross-platform CI** — matrix [macOS, Windows, Linux] × py [3.9–3.12] running unit tests on every PR and main push (`.github/workflows/test.yml`).
- **MCP server** (`dvr mcp`) — stdio Model Context Protocol server exposing 20 tools across `doctor` / `project.*` / `media.*` / `render.*` / `timeline.*` namespaces. Each tool's `inputSchema` is a valid JSON Schema; DvrError surfaces as structured `{errorCode, message, hint}` content. Drop-in `.mcp.json` config shown in README.
- **Workflow Integrations bridge** — bundled `wi-plugin/` (manifest + index.html + server.js) and `dvr install-wi` command for one-shot deployment to Resolve's plugin folder (macOS / Windows / Linux paths supported).
- **`dvr timeline cut --at <TC>`** and **`dvr timeline move --clip <id> --to <TC>`** — dispatched through the WI bridge over localhost HTTP (port 50420). v0.2 cut is implemented in the WI plugin as a placeholder marker (true `SplitClip` deferred to v0.3 pending Resolve API surface); move returns a structured deferred response.
- **New error codes**: `wi_unavailable`, `wi_error`.
- 38 new unit tests (total 178 ≥ 140 baseline).

### Changed
- Compatibility matrix in README: Windows and Linux promoted from "🚧 planned" to ✅ (unit + CI verified; community real-Resolve feedback welcome).
- README restructured to document both Skill (`SKILL.md`) and MCP (`dvr mcp`) integration paths.

### Deferred
- True razor-cut and clip-move via Workflow Integrations require a JS surface Resolve has not yet exposed — tracked for v0.3.
- TestPyPI dry-run workflow lives behind `workflow_dispatch: target=testpypi`.

[0.2.0]: https://github.com/Poechant/davinci-resolve-cli/releases/tag/v0.2.0

## [0.1.0] - 2026-05-14

### Added
- Initial CLI scaffold with five command domains: `doctor`, `project`, `media`, `render`, `timeline`.
- `dvr doctor` — environment diagnostic report (resolve state, version, edition, API paths, issues).
- `dvr project` — `list / open / new / close / save / export / import / current`.
- `dvr media` — `import / list / tag` with `--bin`, `--recursive`, partial-failure reporting, 16 valid flag colors.
- `dvr render` — `presets / submit / status / list / wait / cancel` with async `jobId` state machine persisted to `~/.dvr/jobs.json`.
- `dvr timeline` — `list / current / open / new / clips / marker add/delete/list` with `--dry-run` for marker ops.
- Pluggable output renderer: `--format table|json|yaml`; TTY auto-detection; `DVR_OUTPUT` override.
- Structured error contract: stable `errorCode` enum, JSON-on-stderr emission, sysexits-mapped exit codes.
- `SKILL.md` packaged for AI agent skill systems with five worked examples.
- Bash/Zsh/Fish completion via Typer (`dvr --install-completion`).
- 140 unit tests with `FakeResolve` in-memory state machine; zero real Resolve dependency in CI.

### Deferred to v0.2
- `timeline cut` and `timeline move` — no DaVinciResolveScript public API; requires Workflow Integrations bridge.
- Windows / Linux first-class support (paths are detected, full integration testing pending).
- MCP server packaging.

[0.1.0]: https://github.com/poechant/davinci-resolve-cli/releases/tag/v0.1.0
