# Policy: `externally-managed`

A skill placed and refreshed by **something other than the skills CLI**:
another tool's installer, a plugin system, or a person who maintains the folder
in place by hand. It lives in the store or in an agent's own skills folder and
loads normally, but it has **no lock entry**, by design.

## Rules

- **Never** `npx skills add`, `remove` or `update` it. A `remove` would only
  half-work and an `add` would create a second, drifting copy under CLI
  control.
- **Refresh it through its owner**, with the `refresh` command in its config
  entry.
- **It is not an orphan.** An orphan has no owner and should be deleted
  (`health.md`). These have an owner, so `skill_origin.py --all` lists them
  under *externally managed*, and `skill_origin.py <name>` reports the policy
  and refresh command.
- **To retire one**, uninstall it through its owner, then delete its entry
  from the config.

## Config shape

One entry per externally-managed skill in the config, alongside the git
sources. No `url`, since there is nothing to clone:

```json
{
  "name": "<skill>",
  "policy": "externally-managed",
  "managed_by": "<the tool and command that placed it, or 'hand-maintained'>",
  "refresh": "<command that refreshes it>"
}
```

One owner that ships several skills can list them in one entry with
`"skills": ["<skill>", "<skill2>"]`; `name` is then just a label.
