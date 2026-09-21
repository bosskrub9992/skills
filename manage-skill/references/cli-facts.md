# `skills` CLI facts

vercel-labs/skills, run as `npx skills`. Everything below is **verified on
v1.7.0** — by live runs against a throwaway fixture repo at both scopes, and
where marked *(code)*, by reading the shipped `dist/cli.mjs`. Re-verify after a
version bump: `npx skills --version`. § Changed since 1.5.x lists what older
notes and habits get wrong.

`<scope-flag>` is `-g` for global and nothing for project. `<agents>` is the
config's `agents` list.

---

## Two scopes

| | project (no flag) | global (`-g`) |
|---|---|---|
| lock file | `./skills-lock.json`, `version: 1` | `~/.agents/.skill-lock.json`, `version: 3` (`$XDG_STATE_HOME/skills/.skill-lock.json` when that variable is set) |
| store | `./.agents/skills/<name>` | `~/.agents/skills/<name>` |
| entry fields | `source`, `sourceUrl`, `sourceType`, `ref`, `skillPath`, `computedHash` | `source`, `sourceUrl`, `sourceType`, `ref`, `skillPath`, `skillFolderHash`, `installedAt`, `updatedAt` |

`ref` is present only after a `#branch` install. The project lock carries **no
dates**; it is meant to be committed (`npx skills experimental_install`
restores from it). Everything project-scoped resolves against the **current
directory**, so run from the project root.

**Both locks are keyed by skill name only.** Installing a same-named skill
from a second source silently overwrites the first entry *and* its files.
Nothing warns you. The same name at both scopes is two installs that both
load. `skill_origin.py --all` lists both kinds of collision.

**A global install from a URL whose path is not `owner/repo`-shaped gets no
lock entry** (`https://host/repo.git` with a single path segment): the files
land, nothing tracks them, and the result is an orphan. Project scope does
not have this gap.

## Install layout

| `-a` value | Where the real files go | The agent's own folder |
|---|---|---|
| several agents (verified: `claude-code cursor`) | the store (`.agents/skills/<name>`) | symlink into the store |
| one agent with its own folder (verified: only `claude-code`) | that agent's folder (e.g. `.claude/skills/<name>`) | the real copy; no store entry |
| `--copy` | real copies everywhere | real copy |

Universal agents read `.agents/skills` directly and get no folder of their
own. **Prefer the multi-agent form** so there is exactly one tree to update;
the scripts handle the single-agent layout too. Valid agent ids: run
`npx skills remove -s __x__ -a '?' -y` and read the `Valid agents:` line.

When the CLI detects it is being run by a coding agent it prints
`Agent detected` and goes non-interactive, as if `-y` were passed.

## `update`: always say which scope

`npx skills update [names…] [-g | -p] [-y]`.

- With neither flag, non-interactively: **project** scope if the current
  folder has `skills-lock.json` or `.agents/skills`, otherwise **global**
  *(live)*. With names and no flag it does both scopes *(code)*. Always pass
  `-g` or `-p`.
- Names filter the run: `npx skills update <name> -g -y` touches that skill
  only.
- Each refresh is a child `add <source>[#ref] --skill <name> -y`, one skill at
  a time.

### The two scopes update differently

- **Global** compares each skill's upstream hash with the lock's
  `skillFolderHash` and reinstalls only on a difference. It never looks at
  disk, so a local edit to an installed folder **survives** until upstream
  touches that skill — then it is wiped with no diff, no prompt, no backup.
- **Project** has no hash check: **every `update -p` reinstalls every matched
  skill**. A local edit, or a `local_preview.py` mirror, is gone on the next
  run.

*Why it matters:* `update` is the wrong tool for "did I edit this?" — use
`skill_origin.py`. And editing the installed tree is never a workflow.

### `update` never adds, and only offers to remove in an interactive terminal

- **New upstream skills are never installed** by `update`. You must `add` them.
- **Deleted upstream** is detected, but the removal prompt only appears when a
  human is typing at the terminal. With `-y`, or whenever an agent or a script
  runs it, it prints `Skipping deletion in non-interactive mode.` and leaves
  the skill installed.
- **Moved upstream** (same name, new path) is followed: `update` re-points the
  lock entry's `skillPath` and refreshes the skill.

*Why it matters:* renamed skills stay installed under their old names next to
their successors, with both descriptions competing for routing. Nothing
self-heals; `skill_origin.py --all` is how you find them.

## Branch installs: only the `#branch` suffix works

```bash
npx skills add "<url>#<branch>" <scope-flag> -s <name> -a <agents> -y
```

The lock entry then records `ref: <branch>` — at both scopes — and every later
`update` of that skill follows that branch. Only that skill: siblings from the
same repo keep their own ref.

The suffix is parsed only on a source the CLI recognises as git: `owner/repo`
shorthand, `git@host:…`, `ssh://….git`, `http(s)://….git`, and github.com /
gitlab.com URLs. It is **not** parsed on `file://` URLs or local paths.

Forms that do **not** work:

- A GitLab `/-/tree/<branch>/` URL when the branch name contains a `/`: the
  URL regex splits on `/`, so the ref is silently truncated into a wrong ref
  plus a subpath.
- `<url>.git@<branch>` — the `@` form is only recognised for the
  `owner/repo@ref` shorthand. In `#ref@filter` the part after `@` is a *skill
  filter*, not a ref.

A private host works through whatever your git config already does (SSH keys,
credential helpers, `url.<base>.insteadOf` rewrites): the CLI shells out to
`git clone`.

## A merged-and-deleted branch freezes the skill

Once the branch is gone upstream, `update` cannot clone that `ref` and skips
the skill, every run, until the entry is re-added:

- **Project**: prints `Failed to check for deleted skills from <url>` and
  `Failed to update N skill(s)`.
- **Global**: prints `✗ Failed to check skills from <url>`, then
  `✓ All global skills are up to date`, and exits 0.

**A re-add from the default branch after every merge is mandatory**, and is the
only thing that resets `ref`:

```bash
npx skills add "<url>" <scope-flag> -s <name> -a <agents> -y
```

*Why it matters:* `skill_origin.py --all` flags these as `pinned-to-branch` (any
entry whose `ref` is set and ≠ the source's default branch). That audit catches
both a forgotten PR/MR and a forgotten post-merge re-add.

## `-a` and `-s` take several values

One flag, space-separated values:

```bash
npx skills add <repo> <scope-flag> -s wizard wait-what -a <agents> -y
```

`'*'` works for either. `--all` is shorthand for `--skill '*' --agent '*' -y`.
**Do not combine `--all` with explicit `-a`/`-s`/`-y`** — it overrides and
conflicts. `-l` lists without installing, `--copy` forces real copies.

`No matching skills found for: a b c` with **spaces** between the names means
every name arrived as **one** value: the shell did not word-split (zsh does not
split an unquoted `$var`). Pass names as separate words — an array
`"${names[@]}"`, or literal words.

## `remove`: names and the scope flag, nothing else

```bash
npx skills remove <name> <name2> <scope-flag> -y
```

This removes the store folder, every agent link, and the lock entry.

**Do not pass `-a` to `remove`.** With an agent list — even one that includes
`universal` — it prints `Successfully removed`, deletes only those agents'
links, and leaves the store folder **and the lock entry** in place, because
other universal agents still "use" the store. Also: `remove` rejects `-a '*'`,
and `--all` cannot be combined with names.

Verify, whatever form you used:

```bash
python3 <skill-dir>/scripts/skill_origin.py <name>      # must say "not installed"
```

If a store folder does survive, delete it by hand; it is now an orphan.

## Frontmatter gate

A `SKILL.md` whose YAML frontmatter lacks `name:` or `description:` is
**skipped**: `-l` prints a `⚠ Skipped … missing required frontmatter field(s)`
line and the skill never installs. Frontmatter that is not valid YAML is
skipped too (`yaml-traps.md`). Validate before pushing:

```bash
npx skills add <path-to-clone> -l      # dry run, no install
npx skills add <remote-url> -l         # after pushing
```

Count the skills it lists; a lower number than you expect is the signal.

## Never install from a local path

`npx skills add ./repo …` produces a real install sourced from the working
tree. It drifts from the repo the moment anyone edits and pushes, and nothing
about the result signals "this did not come from the remote". `update` skips
`sourceType: "local"` entries entirely. Use `-l` to validate, push, then
install from the remote URL.

## Nested layouts are discovered

The CLI walks the tree for `**/SKILL.md`, skipping `node_modules`, `.git`,
`dist`, `build`, `__pycache__`. Group directories are flattened:
`skills/<group>/<folder>/SKILL.md` installs as one skill.

**The installed name is the frontmatter `name:`, not the folder name.** A
folder `foo/` whose SKILL.md says `name: bar` installs as `bar`, and `-s foo`
finds nothing. Keep the two equal.

## The lock hashes — do not use them for "is this edited"

`computedHash` / `skillFolderHash` for a generic git source is `sha256` over,
for each file in the folder (recursively, skipping `.git` and `node_modules`),
sorted by relative path: the relative path string, then the raw file bytes
*(code)*. Two reasons a reimplementation will not match:

1. **Sort order is JS `localeCompare`, not byte order.** `evals/evals.json`
   sorts *before* `SKILL.md`.
2. **GitHub-sourced skills store a git tree SHA instead**, taken from the
   GitHub API, so the stored hash can never match one computed over the
   installed folder.

On top of that, a checkout with line-ending conversion (Windows) changes the
bytes. `skill_origin.py` compares file contents against the clone instead,
ignoring CRLF/LF differences.

## Reading a lock by hand

```bash
python3 -c "import json,os;p=os.path.expanduser('~/.agents/.skill-lock.json');d=json.load(open(p,encoding='utf-8'))['skills'];[print(v.get('sourceUrl') or v.get('source'),k,v.get('ref','')) for k,v in sorted(d.items())]"
```

Swap the path for `skills-lock.json` at project scope.

## Other ops

```bash
npx skills list                # project     (add --json for machine output)
npx skills list -g             # global
npx skills <verb> --help       # per-verb flags
```

## Changed since 1.5.x

Older notes, and habits formed on them, get these wrong on 1.7.0:

| 1.5.x | 1.7.0 |
|---|---|
| `update -g` reinstalled a whole repo at the first entry's ref, so one `#branch` install **spread the pin** to every sibling | refresh is per skill; the pin stays on the skill you installed from the branch |
| `remove` always leaked the store folder; the fix was a second `rm -rf` | bare `remove <name>` is clean; the leak now happens only when you pass `-a` |
| a skill moved upstream read as deleted and silently stopped refreshing | `update` follows the move |
| repeating `-s`/`-a` misparsed silently | repeated flags parse correctly; the one-flag form is still the documented one |
| `update` had no name filter and no `-p` | `update [names] [-g\|-p]` |
| a frontmatter-less `SKILL.md` was skipped with no output | `-l` prints a `⚠ Skipped` line |
