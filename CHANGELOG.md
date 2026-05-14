# Changelog

All notable changes to this project will be documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-14 (unreleased)

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
