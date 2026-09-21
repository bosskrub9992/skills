# Policy: `read-only`

Repos you cannot push to — usually public ones. There is no clone and no way to
land a change.

**Never edit the installed folder.** The next update that touches the skill
replaces the whole folder with no warning. To customise one, fork it into a
`direct-push` source under a **new name** and remove the original. The flow is
below.

Which sources use this policy and their install URLs live in the config
(`~/.config/manage-skill/sources.json`). `skill_origin.py --all` prints the
installed and upstream counts per source.

## Rules

- **You install a subset of a public repo on purpose.** Nothing lists or
  installs new upstream skills for you; add the ones you want by name with
  `-s`. `npx skills add <url> -l` shows what a repo offers.
- **A skill deleted or renamed upstream stays installed** under its old name.
  `update` run by an agent never removes it. `skill_origin.py --all` reports
  it as `gone-upstream`, with a rename hint when one exists.
- **Do not use the lock hash to detect local edits.** For GitHub sources it is
  a git tree SHA and never matches the installed folder. `skill_origin.py`
  compares file contents instead, when there is a clone to compare against
  (`cli-facts.md`).

## Flow: add a skill from a public repo

```bash
npx skills add <url> -l                                             # list, install nothing
npx skills add <url> <scope-flag> -s <name> <name2> -a <agents> -y
```

`-s` and `-a` take several space-separated values. Check
`skill_origin.py --all` § Name collisions first: a name another source already
provides is replaced without a warning. A new source also needs a `read-only`
entry in the config, or the health report shows its skills as `source-not-configured`.

## Flow: upgrade a public repo

When a public repo announces a release:

1. `npx skills add <url> -l` to see what the repo offers now, and
   `skill_origin.py --all` to see which of your installed skills from it are
   `gone-upstream` or `moved-upstream`.
2. Install the subset you want, one `-s` with names space-separated.
3. Remove what vanished upstream or that you no longer want:
   `npx skills remove <name> <scope-flag> -y` (no `-a`; `cli-facts.md`).
   `update` will not do it.
4. `npx skills update -g -y` or `npx skills update -p -y` to refresh everything
   that survived at that scope.
5. `skill_origin.py --all`: nothing from that source is `gone-upstream` or `moved-upstream`.

## Flow: customise a read-only skill (fork it)

1. Copy the installed folder into the `direct-push` source's clone under a
   **new name**. `skill_origin.py <orig>` prints the installed dir:
   ```bash
   cp -R <installed dir of orig> <clone>/<new-name>
   ```
   A new name is required. Lock entries are keyed by name, so reusing `<orig>`
   would make two sources fight over one entry.
2. Edit `SKILL.md`: set `name: <new-name>` and rewrite `description` for what
   the fork now does. Keep the original's licence and attribution.
3. Add the index row, commit, push the default branch.
4. Install the fork:
   ```bash
   npx skills add <url> <scope-flag> -s <new-name> -a <agents> -y
   ```
5. **Remove the original, not optional.** Otherwise both descriptions stay
   loaded and compete for routing, and updates keep refreshing the copy you
   just replaced:
   ```bash
   npx skills remove <orig> <scope-flag> -y
   ```
6. Verify: `skill_origin.py <orig>` says it is not installed, and
   `skill_origin.py <new-name>` is CLEAN.
7. Start a **new agent session**. The original's description stays in the
   current session's routing table until then.
