#!/usr/bin/env python3
"""Where did this skill come from, and what state is the install in?

One skill:
  skill_origin.py <skill>     scope, source, policy, pinned ref, clone path, and a
                              file-by-file comparison of the installed folder
                              against the source's default branch.

Every skill you installed (the lock files are the list you chose):
  skill_origin.py --all       one line per locked skill with its scope and state,
                              then the facts you may want to act on: name
                              collisions, orphans, externally-managed skills.

Scopes:
  project        ./skills-lock.json + ./.agents/skills   (npx skills ... )
  global         the home lock + ~/.agents/skills         (npx skills ... -g)
  --scope auto (default) reads every scope that exists. A project install is
  only visible from that project's root; pass --project-dir from elsewhere.

States in --all:
  ok             upstream still has it at the same path; install matches
  differs        installed folder differs from the default branch (you edited it,
                 or upstream moved on; an update would overwrite it)
  deleted        upstream no longer has it; a rename hint is shown when a
                 similar name exists upstream
  moved          upstream still has it, at a new path; the next update follows
                 the move and re-points the lock entry
  pinned-ref     lock entry points at a branch, not the default branch. If that
                 branch merged and was deleted, updates stop for this skill.
                 Fix: re-add from the default branch
  no-compare     source without a local clone; nothing local to diff against
  no-source      the lock's source is not in the config

Read-only. This script never writes anything. It reports; you decide, and the
skills CLI does the work. What to do about each state: references/health.md.

Exit code 3 means no config exists yet: see SKILL.md § First run.
"""

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _skilllib import (  # noqa: E402
    EXTERNAL, READ_ONLY, add_scope_args, classify_unlocked, clone_health,
    closest_names, compare, die, entry_url, export_from_clone, external_skills,
    git, git_sources, has_clone, load_config, lock_entries_for, remote_skills,
    resolve_in_clone, resolve_scopes, rmtree, source_for_entry,
)


def diff_against_default(scope, src, name, skill_path):
    installed = scope.installed_dir(name)
    if not os.path.isdir(installed):
        return None, "not present under %s" % scope.store
    if not has_clone(src):
        return None, "source has no local clone; nothing to compare against"
    clone = src["clone"]
    if not skill_path:
        folder = resolve_in_clone(src, name)
        skill_path = (os.path.relpath(folder, clone).replace(os.sep, "/")
                      + "/SKILL.md") if folder else None
    if not skill_path:
        return None, "no skillPath in lock and not found in clone"
    tmp = tempfile.mkdtemp(prefix="skill-origin-")
    try:
        ref = "origin/" + src["default_branch"]
        if not export_from_clone(clone, ref, skill_path, tmp):
            return None, "%s does not contain %s" % (ref, skill_path)
        return compare(installed, tmp), "%s:%s" % (ref, os.path.dirname(skill_path))
    finally:
        rmtree(tmp)


def has_changes(d):
    return bool(d and (d["added"] or d["removed"] or d["modified"]))


def is_pinned(src, entry):
    ref = entry.get("ref")
    if not ref:
        return False
    default = src.get("default_branch") if src else None
    return default is None or ref != default


def analyse_one(cfg, scope, name, entry):
    src = source_for_entry(cfg, entry)
    info = {
        "skill": name,
        "scope": scope.name,
        "scope_flag": scope.flag,
        "source": src["name"] if src else entry_url(entry),
        "policy": src["policy"] if src else "unknown",
        "source_url": entry_url(entry),
        "install_url": src["url"] if src else entry_url(entry),
        "source_type": entry.get("sourceType"),
        "ref": entry.get("ref") or None,
        "skill_path": entry.get("skillPath"),
        "installed_at": entry.get("installedAt"),
        "updated_at": entry.get("updatedAt"),
        "clone": src.get("clone") if src else None,
        "default_branch": src.get("default_branch") if src else None,
        "installed_dir": scope.installed_dir(name),
        "links": scope.links_for(name),
        "lock_file": scope.lock_path,
        "agents": cfg["agents"],
        "pinned_ref": is_pinned(src, entry),
        "diff": None,
        "diff_note": None,
    }
    if src is None:
        info["diff_note"] = "source not in the config; cannot compare"
        return info
    if has_clone(src):
        git(src["clone"], "fetch", "--quiet", "origin")
    diff, note = diff_against_default(scope, src, name, entry.get("skillPath"))
    info["diff"] = diff
    if diff is None:
        info["diff_note"] = note
    else:
        info["compared_against"] = note
    return info


def print_one(info):
    print("skill          : %s" % info["skill"])
    print("scope          : %s  (CLI flag: %s)"
          % (info["scope"], info["scope_flag"] or "none"))
    print("source         : %s  [%s]" % (info["source"], info["policy"]))
    print("source url     : %s  (%s)" % (info["source_url"], info["source_type"]))
    print("ref            : %s" % (info["ref"] or "(default branch)"))
    if info["pinned_ref"]:
        print("                 !! PINNED REF: installed from branch '%s'; the default"
              % info["ref"])
        print("                    branch is '%s'. If that branch merged and was deleted,"
              % info["default_branch"])
        print("                    updates have stopped. Re-add from the default branch.")
    print("skill path     : %s" % (info["skill_path"] or "-"))
    print("clone          : %s" % (info["clone"] or "(none)"))
    print("installed dir  : %s" % info["installed_dir"])
    for link in info["links"]:
        print("also at        : %s" % link)
    print("lock file      : %s" % info["lock_file"])
    print("installed at   : %s" % (info["installed_at"] or "-"))
    print("updated at     : %s" % (info["updated_at"] or "-"))
    print("agents (-a)    : %s" % " ".join(info["agents"]))
    print()
    d = info.get("diff")
    if d is None:
        print("comparison     : skipped, %s" % info["diff_note"])
        return
    print("compared with  : %s" % info.get("compared_against"))
    if not has_changes(d):
        print("result         : CLEAN, installed copy matches the default branch")
        return
    print("result         : DIFFERS from the default branch")
    print("                 (you edited the install, or the branch moved on;")
    print("                  an update would overwrite the install)")
    for label, key in (("only in install", "added"),
                       ("only upstream  ", "removed"),
                       ("different      ", "modified")):
        if d[key]:
            print("  %s: %s" % (label, " ".join(d[key])))


def external_info(scope, name, meta):
    return {"skill": name, "scope": scope.name, "source": meta["name"],
            "policy": EXTERNAL, "managed_by": meta.get("managed_by"),
            "refresh": meta.get("refresh"),
            "installed_dir": scope.installed_dir(name),
            "links": scope.links_for(name)}


def print_external(info):
    print("skill          : %s" % info["skill"])
    print("scope          : %s" % info["scope"])
    print("policy         : %s" % EXTERNAL)
    print("placed by      : %s" % (info["managed_by"] or "?"))
    print("installed dir  : %s" % info["installed_dir"])
    for link in info["links"]:
        if link != info["installed_dir"]:
            print("also at        : %s" % link)
    print()
    print("No lock entry, and that is correct: something other than the skills")
    print("CLI placed it, so `npx skills` never adds, removes or updates it.")
    print("Not an orphan.")
    if info.get("refresh"):
        print("refresh with   : %s" % info["refresh"])


def analyse_all(cfg, scopes):
    sources, rows, upstream_by_source = [], [], {}
    for src in git_sources(cfg):
        per_scope = [(sc, lock_entries_for(cfg, sc.lock, src)) for sc in scopes]
        installed = sum(len(e) for _, e in per_scope)
        rec = {"source": src["name"], "policy": src["policy"],
               "installed": installed, "upstream": None, "error": None,
               "clone": clone_health(src)}
        upstream = None
        if installed or has_clone(src):
            try:
                upstream = remote_skills(src)
                upstream_by_source[src["name"]] = upstream
                rec["upstream"] = len(upstream)
            except Exception as exc:  # noqa: BLE001
                rec["error"] = str(exc)
        sources.append(rec)

        for scope, entries in per_scope:
            for name in sorted(entries):
                e = entries[name]
                row = {"skill": name, "scope": scope.name, "source": src["name"],
                       "policy": src["policy"], "ref": e.get("ref") or "",
                       "updated_at": (e.get("updatedAt") or "")[:10],
                       "state": "ok", "detail": ""}
                if is_pinned(src, e):
                    row["state"], row["detail"] = "pinned-ref", "ref=%s" % e["ref"]
                elif upstream is None:
                    row["state"], row["detail"] = "unknown", "upstream unreadable"
                elif name not in upstream:
                    hints = closest_names(name, set(upstream) - {name})
                    row["state"] = "deleted"
                    if hints:
                        shown = ["%s%s" % (h, " (already installed)"
                                           if h in scope.lock else "") for h in hints]
                        row["detail"] = "renamed to %s?" % " or ".join(shown)
                    else:
                        row["detail"] = "not upstream"
                elif e.get("skillPath") and upstream[name] != e["skillPath"]:
                    row["state"] = "moved"
                    row["detail"] = "%s -> %s" % (e["skillPath"], upstream[name])
                else:
                    diff, note = diff_against_default(scope, src, name, e.get("skillPath"))
                    if diff is None:
                        row["state"] = "no-compare"
                        row["detail"] = ("read-only, not compared"
                                         if src["policy"] == READ_ONLY else note)
                    elif has_changes(diff):
                        row["state"] = "differs"
                        row["detail"] = "%d changed, %d only local, %d only upstream" % (
                            len(diff["modified"]), len(diff["added"]), len(diff["removed"]))
                rows.append(row)

    known = {(r["scope"], r["skill"]) for r in rows}
    for scope in scopes:
        for name in sorted(scope.lock):
            if (scope.name, name) in known:
                continue
            e = scope.lock[name]
            rows.append({"skill": name, "scope": scope.name, "source": entry_url(e),
                         "policy": "unknown", "ref": e.get("ref") or "",
                         "updated_at": (e.get("updatedAt") or "")[:10],
                         "state": "no-source",
                         "detail": "add this source to the config"})

    collisions = []
    locked_names = sorted({r["skill"] for r in rows})
    for name in locked_names:
        mine = [r for r in rows if r["skill"] == name]
        installed_from = sorted({r["source"] for r in mine})
        offering = [s for s, up in upstream_by_source.items() if name in up]
        also_in = [s for s in offering if s not in installed_from]
        scopes_in = sorted({r["scope"] for r in mine})
        if also_in or len(scopes_in) > 1:
            collisions.append({"skill": name, "installed_from": installed_from,
                               "scopes": scopes_in, "also_in": also_in})

    orphans, external = [], []
    for scope in scopes:
        o, x = classify_unlocked(cfg, scope)
        dirs = scope.skill_dirs()
        orphans += [{"skill": n, "scope": scope.name, "dir": dirs[n]} for n in o]
        external += [{"skill": n, "scope": scope.name, "dir": dirs[n]} for n in x]
    rows.sort(key=lambda r: (r["scope"], r["source"] or "", r["skill"]))
    return sources, rows, collisions, orphans, external


def print_all(cfg, scopes, sources, rows, collisions, orphans, external):
    print("CONFIG  %s" % cfg["path"])
    print("SCOPES")
    for sc in scopes:
        print("  %-8s lock %s%s" % (sc.name, sc.lock_path,
                                    "" if sc.has_lock else "  (no lock file)"))
    print()
    print("SOURCES")
    for s in sources:
        ch = s["clone"]
        if s["error"]:
            state = "!! upstream unreadable: %s" % s["error"]
        elif not ch:
            state = "no clone"
        elif ch.get("error"):
            state = ch["error"]
        else:
            flags = []
            if not ch["on_default"]:
                flags.append("on branch %s" % ch["branch"])
            if ch["behind"]:
                flags.append("behind by %d" % ch["behind"])
            if ch["ahead"]:
                flags.append("ahead by %d (unpushed)" % ch["ahead"])
            if ch["dirty_files"]:
                flags.append("dirty (%d files)" % ch["dirty_files"])
            state = "clone " + (", ".join(flags) or "clean, on default, up to date")
        print("  %-24s %-22s installed %-4s upstream %-4s %s"
              % (s["source"], "[%s]" % s["policy"], s["installed"],
                 s["upstream"] if s["upstream"] is not None else "?", state))
    print()

    print("%-34s %-8s %-24s %-12s %s" % ("SKILL", "SCOPE", "SOURCE", "STATE", "DETAIL"))
    for r in rows:
        print("%-34s %-8s %-24s %-12s %s"
              % (r["skill"], r["scope"], r["source"], r["state"], r["detail"]))
    print()

    counts = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    print("%d locked skills: %s" % (len(rows), ", ".join(
        "%d %s" % (counts[k], k) for k in sorted(counts)) or "none"))
    attention = [k for k in ("deleted", "moved", "pinned-ref", "differs",
                             "no-source", "unknown") if counts.get(k)]
    if attention:
        print("states needing a decision: %s. What each one means and how to act: "
              "references/health.md" % ", ".join(attention))
    print()

    print("NAME COLLISIONS (a name installed in both scopes, or one that another "
          "configured source also offers)")
    if collisions:
        for c in collisions:
            parts = ["installed from %s" % ", ".join(c["installed_from"]),
                     "scope %s" % "+".join(c["scopes"])]
            if c["also_in"]:
                parts.append("also offered by %s" % ", ".join(c["also_in"]))
            print("  %-34s %s" % (c["skill"], "; ".join(parts)))
        print("  Lock entries are keyed by name: installing a name from another source")
        print("  replaces the current install, and the same name in both scopes loads")
        print("  twice. Decide before you `add`.")
    else:
        print("  none")
    print()

    print("ORPHANS (skill folders with no lock entry and no owner in the config)")
    if orphans:
        for o in orphans:
            print("  %-34s %-8s %s" % (o["skill"], o["scope"], o["dir"]))
        print("  No update can see these. Delete, install properly from a source, or")
        print("  record the owner as an externally-managed entry in the config.")
    else:
        print("  none")
    print()

    print("EXTERNALLY MANAGED (no lock entry by design; something else owns them)")
    ext = external_skills(cfg)
    for x in external:
        print("  %-34s %-8s %s" % (x["skill"], x["scope"],
                                   ext[x["skill"]].get("refresh", "")))
    if not external:
        print("  none")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="skill_origin.py",
        description=__doc__.split("\n\n")[0],
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("skill", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", dest="as_json", action="store_true")
    add_scope_args(ap)
    args = ap.parse_args(argv)

    cfg = load_config()
    scopes = resolve_scopes(cfg, args.scope, args.project_dir)

    if args.all:
        sources, rows, collisions, orphans, external = analyse_all(cfg, scopes)
        if args.as_json:
            print(json.dumps({"config": cfg["path"],
                              "scopes": [{"scope": s.name, "lock": s.lock_path,
                                          "has_lock": s.has_lock} for s in scopes],
                              "sources": sources, "skills": rows,
                              "collisions": collisions, "orphans": orphans,
                              "externally_managed": external}, indent=2))
            return 0
        print_all(cfg, scopes, sources, rows, collisions, orphans, external)
        return 0

    if not args.skill:
        ap.error("give a skill name, or --all")

    name = args.skill
    hits = [sc for sc in scopes if name in sc.lock]
    if hits:
        infos = [analyse_one(cfg, sc, name, sc.lock[name]) for sc in hits]
        if args.as_json:
            for info in infos:
                info["verdict"] = ("unknown" if info["diff"] is None else
                                   "differs" if has_changes(info["diff"]) else "clean")
            print(json.dumps(infos[0] if len(infos) == 1 else infos, indent=2))
            return 0
        for i, info in enumerate(infos):
            if i:
                print("\n" + "-" * 60 + "\n")
            print_one(info)
        if len(infos) > 1:
            print("\n!! '%s' is installed in BOTH scopes, so it loads twice. Keep one."
                  % name)
        return 0

    meta = external_skills(cfg).get(name)
    present = [sc for sc in scopes if name in sc.skill_dirs()]
    if meta and present:
        infos = [external_info(sc, name, meta) for sc in present]
        if args.as_json:
            print(json.dumps(infos[0] if len(infos) == 1 else infos, indent=2))
            return 0
        for info in infos:
            print_external(info)
        return 0
    if present:
        die("'%s' exists at %s but has NO lock entry: it is an orphan. No update "
            "will ever touch it. Delete it, or install it properly from a source. "
            "If something other than the skills CLI owns it, add an "
            "externally-managed entry to the config (%s)."
            % (name, present[0].skill_dirs()[name], cfg["path"]))
    die("'%s' is not installed in scope(s): %s"
        % (name, ", ".join("%s (%s)" % (s.name, s.lock_path) for s in scopes)
           or "none found; run from the project root or pass --scope"))


if __name__ == "__main__":
    sys.exit(main())
