# skills

Personal agent skills, installable with the [`skills` CLI](https://github.com/vercel-labs/skills) into any agent it supports.

## Skills

| Skill | Description |
|-------|-------------|
| `manage-skill` | Manage every installed skill across all source repos, at project and global scope — routing by source, four policies (`read-only` / `direct-push` / `branch-then-review` / `externally-managed`), a per-user config, a read-only health report and a local preview |
| `orchestrator-mode` | Turn the agent into an orchestrator that delegates every task to supervised workers in isolated treehouse worktrees — self-contained briefs, a per-class model/effort matrix, Orca or subagent backend, opt-in code review, and no landing without the user's word |

## Install

The CLI installs from the **git remote** — never from a working tree.

```bash
# list what this repo offers, install nothing
npx skills add bosskrub9992/skills -l

# one skill, globally, for the agents you use (-a takes several space-separated ids)
npx skills add bosskrub9992/skills -g -s manage-skill -a <agent-id> <agent-id> -y

# one skill, into the current project
npx skills add bosskrub9992/skills -s manage-skill -a <agent-id> <agent-id> -y
```

`manage-skill` needs Python 3 and `git`. On first use it walks you through
creating `~/.config/manage-skill/sources.json`; nothing machine-specific lives
in this repo.

## Conventions

- One folder per skill; the folder name equals the frontmatter `name:`.
- Validate before pushing: `npx skills add . -l` must list the skill with no `⚠ Skipped` line.
- No machine-specific paths, private hostnames or personal data in any file. This repo is public.
