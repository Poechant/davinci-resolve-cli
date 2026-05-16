<!-- Thanks for the PR. Keep the summary short and stick to one topic per PR. -->

## Summary

<!-- 2-3 lines: what + why. Link the issue if there is one. -->

## Checklist

- [ ] `pytest -q` is green locally (CI matrix will verify on macOS / Windows / Linux × py3.10–3.12)
- [ ] New command has `--format json|yaml|table`, structured error, `--dry-run` if mutating
- [ ] JSON Schema added under `src/dvr/schemas/` and the test validates against it
- [ ] If a CLI verb was added: matching MCP tool registered in `src/dvr/mcp/tools.py`
- [ ] `CHANGELOG.md` entry under a sensible version bump
- [ ] No vendor-specific AI product names in new code/docs (project stays vendor-neutral)

## Notes for reviewers

<!-- Anything subtle? Edge cases? Trade-offs you considered? -->
