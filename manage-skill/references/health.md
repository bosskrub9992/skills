# Health check: reading `skill_origin.py --all`

Policy-independent. The lock files (`./skills-lock.json` for the project,
`~/.agents/.skill-lock.json` globally) are the list of skills you chose to
install; the report checks each one against its source and tells you what
changed. It never changes anything. You decide, and the `skills` CLI does the
work.

```bash
python3 <skill-dir>/scripts/skill_origin.py --all            # every locked skill, then collisions, orphans
python3 <skill-dir>/scripts/skill_origin.py --all --json
python3 <skill-dir>/scripts/skill_origin.py <skill>          # one skill in full
python3 <skill-dir>/scripts/skill_origin.py --all --scope global
```

Run it from the project root, or the project scope is invisible. Run it after
an upstream rename sweep, after merging a skills PR/MR, when a skill behaves
like an old version, or monthly.

## States and what to do

| State | Meaning | What to do |
|---|---|---|
| `in-sync` | upstream still has it at the same path and the install matches | nothing |
| `out-of-sync` | installed folder differs from the default branch | `skill_origin.py <skill>` lists the files. Either someone edited the install (move the edit into the clone, see the policy file) or upstream moved on (`npx skills update <skill> -g\|-p -y`). Either way an update overwrites the install. |
| `gone-upstream` | upstream no longer has it | Usually a rename; the detail names the likely new name and says whether it is already installed. Install the new name if not, then `npx skills remove <old> <scope-flag> -y`. `update` never removes it when an agent runs it. |
| `moved-upstream` | upstream still has it, at a new path | The next `update` of that scope follows the move and re-points the lock entry. Run it. |
| `pinned-to-branch` | lock entry points at a branch, not the default branch | Expected on the skills a `branch-then-review` branch touches while it is in review. Once it is merged, re-add every `pinned-to-branch` name from the default branch (`branch-then-review.md`). If you forgot, updates have been skipping these skills. |
| `not-compared` | source has no clone to diff against | nothing; updates keep it current |
| `source-not-configured` | the lock's source URL is not in the config | add the source with its policy (SKILL.md § First run), or remove the skill |
| `upstream-unreadable` | the source's remote could not be read | fix access or the URL / `default_branch` in the config; the SOURCES block prints the error |

The SOURCES block also reports each clone: on a non-default branch, behind,
ahead (committed but unpushed — the CLI cannot see it), or dirty.

## Name collisions

Lock entries are keyed by skill **name only**. If two of your sources offer the
same name and you run `npx skills add` for it from the second source, the CLI
replaces the first source's lock entry and files without any warning. And a
name installed at **both scopes** is two installs that both load. That is the
CLI's behaviour and this skill cannot change it, so the protection is to know
beforehand: `skill_origin.py --all` lists every installed name that another
configured source also offers, and every name present at both scopes. Before
any `add`, check that list. If the name is on it, report the collision to the
user and let them choose; never pick one on their behalf.

## Orphans

A skill folder — in the store, or a real folder in an agent's own skills
directory — with no lock entry and no owner in the config. Nothing installed it
through the CLI, so no update can ever refresh or remove it, while agents still
load it. A rename leftover, a manual copy, or a `remove` that was given an
`-a` list all end up here.

Delete it (the folder, plus any agent link to it), or install it properly from
a source so it gets a lock entry. If something else owns it — another tool's
installer, or the user maintaining it by hand — it is not an orphan: give it an
`externally-managed` entry in the config (`externally-managed.md`). Ask the
user which; never delete one on your own judgement.

## `local_preview.py`

```bash
python3 <skill-dir>/scripts/local_preview.py <skill>            # dry run
python3 <skill-dir>/scripts/local_preview.py <skill> --apply
```

Replaces the installed folder with a copy of the skill folder from your clone
(a mirror: files deleted in the clone are deleted in the install too), so an
**unsaved** clone edit is visible to the agent immediately, without git and
without the CLI.

- Valid only for `direct-push` and `branch-then-review`. It refuses
  `read-only` and `externally-managed`.
- If the name is installed at both scopes, pass `--scope`.
- The clone is the only source of truth. The preview is a **disposable
  mirror**. At project scope the next `update -p` overwrites it; globally it
  lasts until upstream changes that skill.
- A **body** change lands on the next invocation. A **description** change is
  only visible in a **new agent session**, because descriptions are read at
  session start.

## Flow: rename a skill

A rename is **not** an update. The CLI keys on names, so the old install
survives the rename and both descriptions stay loaded until you remove the old
one.

1. Move the directory with git so history follows: `git mv <old> <new>`.
2. Set the frontmatter `name:` to the new directory name. It **must** equal
   the directory name.
3. Update the repo's index row if it keeps one, and any cross-skill pointers:
   search the repo for `<old>`.
4. Commit and push (a branch and PR/MR under `branch-then-review`).
5. Install the new name:
   `npx skills add <url> <scope-flag> -s <new> -a <agents> -y`
6. **Remove the old name**: `npx skills remove <old> <scope-flag> -y`
7. Verify: `skill_origin.py <old>` says it is not installed, and
   `skill_origin.py <new>` is CLEAN.
8. Start a **new agent session**. The old description stays in the current
   session's routing table until then.

Under `branch-then-review`, steps 5 and 6 wait until after the merge, and the
post-merge re-add applies.

## After acting on the report

Start a **new agent session**: every added, removed or renamed skill changed
the set of descriptions, and the running session still holds the old one.
Re-run `skill_origin.py --all` to confirm a clean report.
