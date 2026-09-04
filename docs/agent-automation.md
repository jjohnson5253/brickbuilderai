# GitHub agent automation

This repository uses two GitHub Copilot custom agents:

- `implementer` implements issues with `gpt-5.6-terra` and puts observable
  desired outcomes plus verification evidence in its pull request.
- `outcome-reviewer` independently checks out that pull request, runs its code,
  applies justified fixes and consolidations, and reviews it with `gpt-5.6-sol`.

The model in each `.github/agents/*.agent.md` profile is the source of truth. The
issue workflow reads that value and also sends it explicitly to the cloud-agent
assignment API, so an API default cannot silently choose a different model.
New issue tasks branch from `staging`, and the automated PR review loop only runs
for pull requests whose base branch is `staging`.

## One-time repository setup

1. Enable Copilot cloud agent and Copilot CLI for the repository/account.
2. For this personally owned repository, create a fine-grained user token that
   can assign Copilot to issues. It needs metadata read plus Actions, contents,
   issues, and pull requests read/write access. Store it as the Actions secret
   `COPILOT_ASSIGNMENT_TOKEN`.
3. Ensure the token owner has a paid Copilot plan and access to both models.
4. Create the labels `agent:implementer` and `agent:outcome-reviewer` if label
   routing will be used.
5. Optionally create the Actions variable `AGENT_REVIEW_MAX_ROUNDS`. It defaults
   to `3`.
6. In **Settings > Copilot > Coding agent**, allow workflows from Copilot-created
   PRs to run without maintainer approval if the loop must be fully automatic.
   Leaving approval required is safer, but pauses each review run for a maintainer.

For organization-owned repositories, allow Copilot CLI usage billed to the
organization. The PR workflow uses the short-lived `GITHUB_TOKEN` and requests
only `copilot-requests: write` plus repository read in the agent job. The agent's
working-tree patch is passed to a separate publishing job, which uses
`COPILOT_ASSIGNMENT_TOKEN` to update the same PR branch and post the result as its
human owner. The reviewing agent never receives a write-capable repository token
or the user token.

## Routing

When an issue is opened, `.github/workflows/assign-issue-agent.yml` selects:

| Labels present when opened | Agent |
| --- | --- |
| `agent:outcome-reviewer` | `outcome-reviewer` |
| `agent:implementer` or neither label | `implementer` |
| Both agent labels | Workflow fails instead of guessing |

Add `<!-- do-not-auto-assign-agent -->` to an issue body to opt out.

The PR loop only runs for same-repository PRs targeting `staging`, authored by
`copilot-swe-agent[bot]` whose body contains
`<!-- agent-role: implementer -->`. That marker is required by the implementer
profile. Fork PRs and human PRs are deliberately excluded because running an
agent against untrusted pull request content with a write-capable token is unsafe.
The workflow also restores the reviewer profile from the PR's base commit before
execution, so the implementation PR cannot rewrite its own reviewer or model.

For each new head SHA, the reviewer runs once and returns `PASS`, `UPDATED`, or
`CHANGES_REQUESTED`. An `UPDATED` result is committed to the same PR branch by the
publishing job and triggers another review. A remaining change request mentions
`@copilot`, allowing the original cloud-agent session to update its PR. The round
cap prevents an infinite agent-to-agent loop.

## Important GitHub limitation

Copilot code review and Copilot cloud-agent custom profiles are separate features.
Native automatic code review can be enabled in repository rulesets and can review
every push, but GitHub does not expose per-review custom-agent or model selection.
This repository therefore runs the `outcome-reviewer` custom profile through
Copilot CLI in Actions, where both the profile and its model are deterministic.

The issue-assignment API and several agent capabilities are preview features and
may change. Pinning the CLI makes workflow behavior more reproducible; update the
pinned `@github/copilot` version deliberately.
