#!/usr/bin/env python3
"""Mirror a clone's copy of a skill over the installed folder so the agent sees it now.

Bypasses git and the `skills` CLI: replaces the installed folder with a copy of
`<clone>/<skill path>/` (files deleted in the clone are deleted in the install
too). Use it to try an *unsaved* clone edit without pushing.

The clone is the only source of truth. The preview is a disposable mirror: the
next update or add of that skill overwrites it.

Valid only for `direct-push` and `branch-then-review` sources. Refuses
`read-only` (no clone to preview from, and editing the installed folder is never
how you change one: fork it instead) and `externally-managed` (something else
owns it).

Dry run by default. Nothing is written without --apply.

Exit code 3 means no config exists yet: see SKILL.md § First run.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _skilllib import (  # noqa: E402
    EDITABLE, EXTERNAL, READ_ONLY, add_scope_args, die, entry_url,
    external_skills, load_config, mirror, resolve_in_clone, resolve_scopes,
    source_for_entry,
)

REMINDERS = [
    "A description change is only visible in a NEW agent session: descriptions "
    "are read at session start, bodies on invocation.",
    "The next update or add of this skill overwrites the preview without "
    "warning. The clone is the source of truth; commit and push to make it stick.",
]


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="local_preview.py",
        description=__doc__.split("\n\n")[0],
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("skill")
    ap.add_argument("--apply", action="store_true", help="actually mirror")
    ap.add_argument("--json", dest="as_json", action="store_true")
    add_scope_args(ap)
    args = ap.parse_args(argv)

    cfg = load_config()
    scopes = resolve_scopes(cfg, args.scope, args.project_dir)
    name = args.skill

    hits = [sc for sc in scopes if name in sc.lock]
    if len(hits) > 1:
        die("'%s' is installed in both scopes; pass --scope project or --scope "
            "global to choose which install to overwrite." % name)
    if not hits:
        meta = external_skills(cfg).get(name)
        if meta:
            die("'%s' is %s (placed by %s), not installed by the skills CLI; "
                "there is no clone to preview from. Refresh it with: %s"
                % (name, EXTERNAL, meta.get("managed_by", "?"),
                   meta.get("refresh", "(see the config)")))
        die("'%s' has no lock entry in scope(s): %s. If the folder exists it is "
            "an orphan; install it from a source first."
            % (name, ", ".join(s.name for s in scopes) or "none found"))

    scope = hits[0]
    entry = scope.lock[name]
    src = source_for_entry(cfg, entry)
    if src is None:
        die("'%s' comes from %s, which is not in the config (%s); add it there first."
            % (name, entry_url(entry), cfg["path"]))
    if src["policy"] == READ_ONLY:
        die("'%s' comes from %s, a read-only source. Never edit a read-only "
            "skill in place: the next update that touches it wipes your "
            "changes. To customise it, fork it into a source you own under a "
            "NEW name (references/read-only.md)." % (name, src["name"]))
    if src["policy"] not in EDITABLE:
        die("'%s' comes from %s [%s]; nothing to preview." % (name, src["name"], src["policy"]))

    folder = resolve_in_clone(src, name, entry.get("skillPath"))
    if folder is None:
        die("could not find %s/SKILL.md anywhere under %s. Is the clone on a "
            "branch that has it?" % (name, src["clone"]))

    dest = scope.installed_dir(name)
    plan = {"skill": name, "scope": scope.name, "source": src["name"],
            "policy": src["policy"], "from": folder, "to": dest,
            "applied": args.apply, "reminders": REMINDERS}

    if args.apply:
        mirror(folder, dest)

    if args.as_json:
        print(json.dumps(plan, indent=2))
        return 0

    print("skill   : %s" % name)
    print("scope   : %s" % scope.name)
    print("source  : %s [%s]" % (src["name"], src["policy"]))
    print("from    : %s" % folder)
    print("to      : %s" % dest)
    print()
    if not args.apply:
        print("Dry run. Re-run with --apply to mirror it.")
        return 0
    print("preview installed.")
    for r in REMINDERS:
        print("  ! " + r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
