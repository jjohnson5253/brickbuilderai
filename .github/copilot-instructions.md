# Working preferences

- Proceed autonomously on routine, reversible work (e.g. editing code, running
  existing tests/builds, pushing to a feature/PR branch, merging non-`main`
  branches into other non-`main` branches). Don't stop to ask for confirmation
  on these.
- Only ask a clarifying question when a decision is genuinely ambiguous (multiple
  reasonable approaches with real tradeoffs), destructive, or hard to undo (e.g.
  force-pushing over others' work, deleting data, rotating or revoking
  credentials).
- When in doubt, prefer taking the reversible/lower-risk action and mentioning what
  you did, over pausing to ask.
- **Never merge or push directly to `main`.** All changes to `main` must go
  through a pull request, even for small fixes, infra scripts, or reverts.
  Open a PR and let it merge normally instead of committing straight to `main`.
