---
name: manage-skill
description: Manage every agent skill installed on this machine, at project scope and global scope, across all of its source repos — add, install, update, remove, list, sync, prune, and safely edit a skill's content. Use when the user asks to add/install/update/remove/list skills, "which repo does this skill come from", "where does this skill live", "check my skills", "which skills are stale", "prune stale skills", "install from branch", "install a skill from my PR branch", "local preview", "preview my skill edit", "the install command is broken", "how do I install my skills", "why is this skill out of date", "I renamed a skill", "this skill has no lock entry", "orphan skill", "who manages this skill", renaming or moving a skill between repos, upgrading a third-party skill repo, forking a public skill, or a duplicate/old-name skill still loading. Also use — the easy one to miss — when a task changes the text or scripts of an installed skill ("fix the URL in that skill", "reword the description", "edit SKILL.md"), or touches a path under `.agents/skills/` or an agent's own skills folder, because the installed tree is a build output. Covers the `skills` CLI (npx skills), both lock files (`./skills-lock.json` and `~/.agents/.skill-lock.json`), the per-user config, and the four per-source policies (read-only, direct-push, branch-then-review, externally-managed). Apply in Thai too ("ลง skill", "ลบ skill", "อัพเดท skills", "แก้ skill").
---

# Manage skills

Skills on a machine come from **several upstream repos**, installed at **two
scopes**. There is no "the" skills repo. Everything here keys off two questions:

> **Which source does this skill come from, and what is that source's policy?**
> **Which scope is it installed at — project or global?**

Answer them first, then read that policy's file — SKILL.md plus one policy file
is the whole context you need. Never edit an installed folder as a way of
changing a skill: the installed tree is a *build output*.

Authoring *content* (frontmatter, structure, quality bar) belongs to a
skill-authoring skill if one is installed. This skill owns the repos, the CLI,
and the sync loop.

## Conventions used in every command

- `<skill-dir>` is the folder that holds this SKILL.md. Run the scripts as
  `python3 <skill-dir>/scripts/<script>.py` — `python` where `python3` is not
  on PATH (Windows). Python 3 stdlib and `git` only.
- `<scope-flag>` is `-g` for a global install and **nothing** for a project
  install. `update` is the exception: always pass `-g` or `-p`, because a bare
  `update` run by an agent silently picks one scope (`references/cli-facts.md`).
- `<agents>` is the `agents` list from the config, space-separated.
  `skill_origin.py <name>` prints the scope flag and the agents for you.

| | project scope | global scope |
|---|---|---|
| lock file | `./skills-lock.json` | `~/.agents/.skill-lock.json` |
| real files | `./.agents/skills/<name>` | `~/.agents/skills/<name>` |
| per-agent link | `./<agent folder>/skills/<name>` | `~/<agent folder>/skills/<name>` |
| seen from | that project's root only | anywhere |

Project-scope commands and scripts must run **from the project root**.

## First run: create the config

Which source follows which policy is the user's own data, so it lives on their
machine, not in this skill: `~/.config/manage-skill/sources.json`
(`$MANAGE_SKILL_CONFIG` overrides the path). A script that exits with **code
3** is telling you the file does not exist yet. Create it *with* the user:

1. From the project root: `python3 <skill-dir>/scripts/init_config.py --discover`.
   It reads both lock files and prints the sources in use, their skills per
   scope, each remote's default branch, the agent skill folders it found, and
   skill folders that have no lock entry. It writes nothing.
2. For each source, ask: **can you push to this repo?**
   - No → `read-only`.
   - Yes → ask: **is its default branch protected, or do changes need
     review?** No → `direct-push`. Yes → `branch-then-review`. Both need the
     path of the user's clone; if there is none, offer to clone it (ask first)
     and confirm `default_branch`.
3. Ask which agents the user runs. That list is `agents`, passed as `-a` on
   every install (valid ids: `references/cli-facts.md`). `agent_skill_dirs`
   comes from the discovery output; confirm it.
4. For each unlocked folder, ask who owns it. Another tool's installer, or the
   user maintaining it by hand → an `externally-managed` entry with
   `managed_by` and `refresh`. Nobody → leave it out; it is an orphan and the
   health report will say so.
5. Show the finished JSON, get a yes, then pipe it to
   `python3 <skill-dir>/scripts/init_config.py --write`. Shape:
   `scripts/sources.example.json`.
6. `init_config.py --check`, then `skill_origin.py --all`.

Later changes — a new source, a moved clone — are edits to that same file:
show the change, get a yes, then `init_config.py --check`. A `no-source` state
in the health report means a lock entry's source is missing from the config.

## Routing rule

```bash
python3 <skill-dir>/scripts/skill_origin.py <name>
```

It prints the scope, the source, its policy, the pinned ref, the clone path,
and whether the install is edited or stale. Then open the policy file below and
follow its flow.

If the skill is **not** in a lock file it was not installed by the CLI. It is
either an **orphan** (delete it, or install it properly — no update will ever
touch it) or **externally-managed** (something else owns it — leave it alone).
`skill_origin.py` tells you which; `references/health.md` § Orphans has the
rule.

## The four policies

| Policy | When | Flow in one line | Detail |
|---|---|---|---|
| **`read-only`** | a repo you cannot push to | never edit; to customise, fork into a repo you own under a **new name**, then remove the original | `references/read-only.md` |
| **`direct-push`** | your repo, default branch **not protected** | edit the clone → **loop question** → commit → push the default branch → update | `references/direct-push.md` |
| **`branch-then-review`** | default branch **protected**, or changes need review | branch → **loop question** → push → install **every skill the diff touches** with `#branch` → open the PR/MR → **after merge, re-add the same list from the default branch** | `references/branch-then-review.md` |
| **`externally-managed`** | something other than the CLI places it | never touch it with `npx skills`; refresh through its owner | `references/externally-managed.md` |

Lock entries are keyed by name alone, so two sources offering one name — or
one name installed at both scopes — is a decision to make before you install:
**`references/health.md`** § Name collisions.

For a **new** install, suggest the scope the source's other skills already use
(`skill_origin.py --all` shows it). When that does not settle it, ask; a skill
installed at the wrong scope is a skill nobody can find.

## Approval: ask once for the loop, not once per step

Repo conventions usually gate `git commit`, `git push` and PR/MR creation
separately. Applied literally to `direct-push` and `branch-then-review`, that
turns the sync loop — commit → push → reinstall from the remote, repeated per
iteration — into three prompts per edit, and the loop is the whole point of
installing through the CLI (git-versioned, agent-independent, never from a
working tree). The conventions bind the agent, not the user, so the fix is to
let the user decide the shape of the approval **before the first commit**, not
to skip it:

> This edit loops **commit on `<branch>` → push to `origin <branch>` →
> `npx skills add "<url>#<branch>" <scope-flag> -s <names> -a <agents> -y`**,
> repeated per iteration. Approve the loop for this session, or gate each step?

- **Loop approved**: run all three per iteration without re-asking. The grant
  covers *this* repo and branch, *these* skill names, *this* session. A new
  branch, repo or name re-asks.
- **Gate each step**: ask before every commit, push and reinstall.
- **Never inside the grant**: opening the PR/MR (outward-facing — always its
  own question), pushing a `branch-then-review` default branch, merging,
  marking a PR/MR ready. For `direct-push` the loop *is* the default branch;
  the question must say so.
- A skill may not grant itself this; only the user's answer does. Do not
  infer it from a previous session or an earlier "commit and push".

## `local_preview.py`

```bash
python3 <skill-dir>/scripts/local_preview.py <skill>            # dry run; --apply to mirror
```

Copies the skill folder from your clone over the installed one so the agent
sees the edit now. `direct-push` and `branch-then-review` only. The preview is
disposable — the next update of that skill overwrites it — and a
**description** change needs a new agent session. Details:
`references/health.md`.

## Health check

```bash
python3 <skill-dir>/scripts/skill_origin.py --all
```

Read-only. One line per installed skill with its scope and state (`ok`,
`differs`, `deleted` with a rename hint, `moved`, `pinned-ref`), then name
collisions, orphans and externally-managed skills. It reports; you decide; the
`skills` CLI does the work. What each state means and how to act:
**`references/health.md`**.

## Non-negotiables

- The CLI installs from the **git remote, never your working tree**. Push before `add`/`update`.
- **Never** `npx skills add <local path>` for a real install — it silently drifts from the repo. Use `-l` to validate frontmatter without installing.
- **Never edit an installed folder** to change a skill. A project-scope `update` reinstalls every skill every time, so the edit is gone on the next run; a global one survives only until upstream changes.
- `update` **always with `-g` or `-p`**. Bare, an agent-run `update` picks project scope when the current folder has project skills and global otherwise, without saying so.
- `remove` takes **names and the scope flag only**: `npx skills remove <name> <scope-flag> -y`. With an `-a` list it reports success and leaves the files and the lock entry behind. Verify with `skill_origin.py <name>`.
- `update` **never adds** a new upstream skill, and offers to remove a deleted one only when run by hand in an interactive terminal, never from inside an agent.
- A `#branch` install **pins** that skill to the branch. Once the branch is deleted upstream the skill stops updating; re-add it from the default branch after every merge.
- A `SKILL.md` whose frontmatter lacks `name:` or `description:`, or is not valid YAML, is **skipped**: `references/yaml-traps.md`.

Mechanism and verification for each, on CLI v1.7.0: **`references/cli-facts.md`**.

## Scripts

The `skills` CLI does the installing, updating and removing. The scripts are
helpers around it, with `--help` on each and JSON output for machines:

- `scripts/skill_origin.py <skill>` / `--all` is **read-only**. It reads the
  lock files and the repos and tells you what state each install is in.
- `scripts/local_preview.py <skill>` writes only with `--apply`, and only into
  the installed folder it mirrors.
- `scripts/init_config.py` writes only with `--write`, and only the config file.

All three take `--scope project|global|auto` (default `auto`: every scope that
exists) and `--project-dir`.
