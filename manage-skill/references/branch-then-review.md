# Policy: `branch-then-review`

You have a clone of the repo, but its default branch is protected or changes
need review. Edit on a branch, install from that branch while iterating, open
a PR/MR, and **re-add from the default branch after the merge**.

Which sources use this policy, and each one's clone path, remote URL and
default branch, live in the config (`~/.config/manage-skill/sources.json`).
`skill_origin.py <name>` prints them for an installed skill, along with its
scope flag and the `-a` agents. Nothing below is specific to one repo or one
git host.

> ## The one rule that is easy to get wrong
>
> A branch install pins the lock entry's `ref` to your branch. Once that branch
> is merged and deleted upstream, the CLI can no longer clone that ref and the
> skill **stops updating** — at global scope without even a failing exit code
> (`cli-facts.md`). Re-add every skill you installed from the branch from the
> default branch after every merge. `skill_origin.py --all` flags each one as
> `pinned-to-branch`, so a forgotten re-add is always visible.

> ## The other rule: install what the branch touches, not what its title says
>
> One PR/MR often edits several skill folders — a procedure plus the shared
> checklist it links into under a sibling skill. The CLI installs per skill
> name, so installing only the titled skill leaves the sibling on the default
> branch and the two halves out of sync locally. Always derive the skill list
> from the diff:
> ```bash
> git -C <clone> fetch origin
> git -C <clone> diff --name-only origin/<default_branch>...origin/<branch>
> ```
> For each changed file, walk up to the nearest folder that holds a
> `SKILL.md`; that folder is a skill to install (its name is the frontmatter
`name:`, normally the folder name). In bash:
> ```bash
> git -C <clone> diff --name-only origin/<default_branch>...origin/<branch> \
>   | xargs -n1 dirname | while read d; do
>       while [ "$d" != "." ] && [ ! -f "<clone>/$d/SKILL.md" ]; do d=$(dirname "$d"); done
>       [ "$d" != "." ] && basename "$d"; done | sort -u
> ```
> Pass every name to one `-s`. Use the same list for the post-merge re-add.

## Flow: edit a skill

Read `clone`, `url` and `default_branch` for the source before starting.

1. **Sync the clone to the default branch.** A branch cut from a stale base
   produces a conflict-heavy PR/MR.
   ```bash
   git -C <clone> fetch origin
   git -C <clone> switch <default_branch> && git -C <clone> pull --ff-only
   git -C <clone> switch -c <branch>
   ```
2. Edit the skill folder inside the clone. Any folder holding a `SKILL.md` is
   a skill; a nested layout (`skills/<group>/<name>/`) installs as one skill,
   named by its frontmatter `name:`.
3. *(optional)* `local_preview.py <name> --apply` to see the edit in the agent
   before committing. See `health.md`.
4. Validate the CLI still parses it: `npx skills add <clone> -l`. The skill
   must be listed, with no `⚠ Skipped` line for it (`yaml-traps.md`).
5. **Run the conflict check, then commit and push the branch.** Steps 5–7 are
   one loop. Before the first commit check the source's `autonomy`, the
   clone's convention files and the session's instructions (SKILL.md §
   Autonomy). No conflict: name the branch, the remote and the exact `-s` list
   in one line and go. Conflict: ask once for the loop, quoting the rule.
   Opening the PR/MR (step 8) is never covered either way.
6. **Install from the branch — every skill the diff touches.** This is the
   only way the CLI sees an unmerged change. Get the names from the diff (rule
   above), not from the PR/MR title:
   ```bash
   npx skills add "<url>#<branch>" <scope-flag> -s <name> <sibling> ... -a <agents> -y
   ```
   Only the `#branch` suffix works as a ref (`cli-facts.md`). Each lock entry
   now carries `ref: <branch>`; `skill_origin.py --all` must list exactly
   those names as `pinned-to-branch`.
7. Iterate: edit, commit, push, then repeat step 6 with the same list, without
   re-asking.
8. Open the PR/MR against the default branch — **ask first, always**; neither
   `autonomy: auto` nor a loop grant covers it. Follow the repo's own conventions file if it has
   one.
9. **After the merge, mandatory.** Re-add from the default branch to clear the
   pinned ref. The list is every skill the diff touched plus any other
   `pinned-to-branch` skill from this source:
   ```bash
   git -C <clone> switch <default_branch> && git -C <clone> pull --ff-only
   python3 <skill-dir>/scripts/skill_origin.py --all          # note the pinned-to-branch rows
   npx skills add "<url>" <scope-flag> -s <name> <sibling> ... -a <agents> -y
   python3 <skill-dir>/scripts/skill_origin.py --all          # no pinned-to-branch rows left
   ```

## Flow: install an existing PR/MR branch

Someone (you, earlier, or a teammate) already pushed the branch and opened the
PR/MR; you only want its content live locally while it is in review.

1. `git -C <clone> fetch origin`, then list the skills the branch touches
   (rule above). Do not trust the title — it usually names one skill.
2. Step 6 of the edit flow with that full list.
3. Verify each installed folder carries the change, e.g. search for a string
   the branch adds in every touched skill's installed folder.
4. Step 9 after the merge, same list.

## Flow: add a new skill

Same as editing, plus: create `<name>/SKILL.md` with `name:` and
`description:` frontmatter (a file without both is skipped by the CLI), and
add the repo's index row if it keeps one. The post-merge step above is also
the first default-branch install of the new name, since `update` never adds.
