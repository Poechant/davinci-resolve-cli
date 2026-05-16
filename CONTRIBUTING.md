# Contributing to davinci-resolve-cli

Thanks for considering a contribution! This project is small, opinionated, and easy to onboard onto.

If you are an **AI coding agent** (Cursor / Codex / Aider / Continue / …) being asked to help a contributor, read [`AGENTS.md`](AGENTS.md) first — it encodes the hard rules.

If you are a **human contributor**, read this file. The rules in `AGENTS.md` also apply to you, but this file is the friendlier entry point.

## Quick start

```bash
git clone https://github.com/Poechant/davinci-resolve-cli.git
cd davinci-resolve-cli
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q   # 184+ tests, no Resolve required
```

You can hack on most commands without DaVinci Resolve installed, thanks to the in-memory `FakeResolve` fixture in `tests/conftest.py`. You only need Resolve running for `pytest -m integration` and for sanity-checking real behavior via `.venv/bin/dvr doctor`.

## How to propose a change

1. **Open an issue first** for anything bigger than a typo or a one-line bug fix. Surface the use case, not just the patch — we'd rather tweak the design once than five times in review.
2. **Branch from `main`** (`git checkout -b feat/your-thing` or `fix/your-thing`).
3. **TDD**: failing test first, then code. See `AGENTS.md` for the full checklist; the short version is below.
4. **One topic per PR.** A doc patch + a feature + a refactor in one PR makes review three times harder.
5. **Open a PR** against `main`. CI runs the matrix on macOS / Windows / Linux × Python 3.10 / 3.11 / 3.12. Green is required.

## The 60-second contribution checklist

- [ ] `pytest -q` is green locally
- [ ] New command has `--format json|yaml|table`, structured error, `--dry-run` if it mutates
- [ ] Output goes through a JSON Schema (`src/dvr/schemas/`) — and the test validates against it
- [ ] If you added a CLI verb, you also registered a matching MCP tool in `src/dvr/mcp/tools.py`
- [ ] `CHANGELOG.md` entry under a sensible version bump
- [ ] No vendor-specific AI product names in new code/docs — the project stays vendor-neutral on AI agents
- [ ] PR title is imperative present tense: "Add subtitle import command", not "Adding..." or "I added..."

## What we welcome

- Bug reports with reproduction + `dvr doctor --format json` output
- New subcommands inside the existing five domains (especially: `media`, `render`, `timeline`)
- Cross-platform fixes (Windows users especially welcome — Linux & macOS authors test there least)
- Documentation improvements, especially the Cookbook
- Skill / MCP examples — share what you've gotten an agent to do well

## What we'll usually push back on

- Adding a new top-level command domain (talk first — five existing ones cover most of Resolve)
- New runtime dependencies (we're at typer / rich / pyyaml / jsonschema / mcp — adding one needs justification)
- Stylistic-only rewrites (we use ruff defaults; please don't reformat history)
- Anything that lowers the Python floor or weakens schemas

## Reporting security issues

Email `zhongchao.ustc@gmail.com` privately. Please don't open a public issue for vulnerabilities until we've had a chance to ship a fix.

## License

By contributing, you agree your changes are licensed under the project's [MIT License](LICENSE).
