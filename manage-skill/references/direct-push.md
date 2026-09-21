# Policy: `direct-push`

You own the repo and its default branch is not protected. Edit in the clone,
commit, push the default branch, refresh. No branch, no PR/MR, no review gate.

Which sources use this policy, and each one's clone path, remote URL and
default branch, live in the config (`~/.config/manage-skill/sources.json`).
`skill_origin.py <name>` prints them for an installed skill, along with its
scope flag and the `-a` agents.

## Flow: edit a skill

1. Edit the skill folder inside the **clone** — never the installed folder.
2. *(optional)* `local_preview.py <name> --apply` to see the edit in the agent
   before committing. See `health.md`.
3. Validate the CLI still parses it: `npx skills add <clone> -l`. The skill
   must be listed, with no `⚠ Skipped` line for it (`yaml-traps.md`).
4. **Ask the loop question, then commit and push the default branch.** Steps
   4–5 repeat per iteration; before the first commit ask the user once whether
   to approve the loop for this session or gate each step (SKILL.md §
   Approval). Say explicitly that the push lands on the default branch.
5. Refresh the install, naming the skill and the scope:
   ```bash
   npx skills update <name> -g -y        # global install
   npx skills update <name> -p -y        # project install, from the project root
   ```
   If `skill_origin.py <name>` showed a pinned ref, `update` would follow that
   branch; re-add from the default branch instead:
   ```bash
   npx skills add <url> <scope-flag> -s <name> -a <agents> -y
   ```
6. Verify: `skill_origin.py <name>` reports CLEAN.

## Flow: add a new skill

1. Create `<name>/SKILL.md` with `name:` and `description:` frontmatter. A file
   without both is skipped by the CLI, and `name:` must equal the directory
   name.
2. Add the repo's index row if it keeps one.
3. Validate (`npx skills add <clone> -l`), then commit and push the default
   branch (loop question first, as in the edit flow).
4. Install it once by name. `update` never adds a new skill. Pick the scope
   the source's other skills use, or ask:
   ```bash
   npx skills add <url> <scope-flag> -s <name> -a <agents> -y
   ```

This is also where a forked `read-only` skill lands. See `read-only.md`.

## Flow: delete a skill

1. `git rm -r <name>/`, drop its index row, commit, push.
2. Remove the install — names and the scope flag only, no `-a`
   (`cli-facts.md`):
   ```bash
   npx skills remove <name> <scope-flag> -y
   ```
3. Verify: `skill_origin.py <name>` says it is not installed.
