#!/usr/bin/env python3
"""Create and check the per-user manage-skill config.

The config lives outside the skill, on the user's machine:
  ~/.config/manage-skill/sources.json      (override with $MANAGE_SKILL_CONFIG)

  init_config.py --path        print where the config is read from
  init_config.py --discover    read the lock files and skill folders and print,
                               as JSON, everything needed to propose a config:
                               the sources in use, their skills per scope, each
                               remote's default branch, the agent skill folders
                               found, and skill folders that have no lock entry
  init_config.py --write       read a config as JSON on stdin, validate it, and
                               write it. Refuses to replace an existing config
                               without --force
  init_config.py --check       validate the existing config

--discover and --check never write. --write is the only writer, and only to
the config path. The interview that turns --discover output into a config is
in SKILL.md § First run; the shape is in scripts/sources.example.json.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _skilllib import (  # noqa: E402
    EXIT_NO_CONFIG, POLICIES, READ_ONLY, Scope, add_scope_args, canonical_url,
    config_path, die, entry_url, load_config, remote_head_branch, resolve_scopes,
    validate_config,
)


def detect_agent_dirs(roots):
    found = []
    for root in roots:
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for d in names:
            if not d.startswith(".") or d == ".agents":
                continue
            rel = "%s/skills" % d
            if rel not in found and os.path.isdir(os.path.join(root, d, "skills")):
                found.append(rel)
    return found


def install_url(entry):
    url = entry_url(entry)
    if entry.get("sourceType") == "github" and re.match(r"^[^/:\s]+/[^/:\s]+$", url):
        return "https://github.com/%s.git" % url
    return url


def discover(args):
    roots = [os.path.abspath(args.project_dir or os.getcwd()), os.path.expanduser("~")]
    agent_dirs = detect_agent_dirs(roots)
    stub = {"agent_skill_dirs": agent_dirs}
    if args.scope == "auto":
        scopes = resolve_scopes(stub, "auto", args.project_dir)
    else:
        scopes = [Scope(stub, args.scope, args.project_dir)]

    sources = {}
    for sc in scopes:
        for name, entry in sorted(sc.lock.items()):
            key = canonical_url(entry_url(entry), entry.get("sourceType"))
            rec = sources.setdefault(key, {
                "url": install_url(entry), "source_type": entry.get("sourceType"),
                "skills": {}, "pinned": {}})
            rec["skills"].setdefault(sc.name, []).append(name)
            if entry.get("ref"):
                rec["pinned"]["%s:%s" % (sc.name, name)] = entry["ref"]

    used = set()
    out_sources = []
    for key in sorted(sources):
        rec = sources[key]
        parts = key.split("/")
        name = parts[-1]
        if name in used and len(parts) > 1:
            name = "%s-%s" % (parts[-2], parts[-1])
        used.add(name)
        rec["suggested_name"] = name
        rec["suggested_policy"] = READ_ONLY
        rec["default_branch"] = (None if args.no_network
                                 else remote_head_branch(rec["url"]))
        out_sources.append(rec)

    unlocked = []
    for sc in scopes:
        for name, path in sorted(sc.skill_dirs().items()):
            if name not in sc.lock:
                unlocked.append({"skill": name, "scope": sc.name, "dir": path})

    path = config_path()
    print(json.dumps({
        "config_path": path,
        "config_exists": os.path.isfile(path),
        "policies": list(POLICIES),
        "scopes": [{"scope": s.name, "root": s.root, "lock": s.lock_path,
                    "has_lock": s.has_lock, "locked_skills": len(s.lock)}
                   for s in scopes],
        "agent_skill_dirs": agent_dirs,
        "sources": out_sources,
        "unlocked_folders": unlocked,
    }, indent=2))
    return 0


def write(args):
    path = config_path()
    if os.path.exists(path) and not args.force:
        die("config already exists at %s. Show the user the difference and get "
            "a yes before re-running with --force." % path)
    try:
        cfg = json.loads(sys.stdin.read())
    except ValueError as exc:
        die("stdin is not valid JSON: %s" % exc)
    problems = validate_config(cfg)
    if problems:
        die("refusing to write an invalid config:\n  - " + "\n  - ".join(problems))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("wrote %s (%d sources)" % (path, len(cfg["sources"])))
    return 0


def check(_args):
    cfg = load_config()
    print("ok: %s (%d sources, agents: %s)"
          % (cfg["path"], len(cfg["sources"]), " ".join(cfg["agents"])))
    for src in cfg["sources"]:
        clone = src.get("clone")
        if clone and not os.path.isdir(os.path.join(clone, ".git")):
            print("  warning: source '%s': clone %s is not a git checkout"
                  % (src["name"], clone))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="init_config.py",
        description=__doc__.split("\n\n")[0],
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--path", action="store_true")
    mode.add_argument("--discover", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="with --write: replace an existing config")
    ap.add_argument("--no-network", action="store_true",
                    help="with --discover: skip the default-branch lookup")
    add_scope_args(ap)
    args = ap.parse_args(argv)

    if args.path:
        print(config_path())
        return 0 if os.path.isfile(config_path()) else EXIT_NO_CONFIG
    if args.discover:
        return discover(args)
    if args.write:
        return write(args)
    return check(args)


if __name__ == "__main__":
    sys.exit(main())
