import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

EXTERNAL = "externally-managed"
READ_ONLY = "read-only"
DIRECT_PUSH = "direct-push"
BRANCH_THEN_REVIEW = "branch-then-review"
POLICIES = (READ_ONLY, DIRECT_PUSH, BRANCH_THEN_REVIEW, EXTERNAL)
EDITABLE = (DIRECT_PUSH, BRANCH_THEN_REVIEW)

AUTONOMY_AUTO = "auto"
AUTONOMY_ASK = "ask"
AUTONOMY = (AUTONOMY_AUTO, AUTONOMY_ASK)

SCOPES = ("project", "global")
EXIT_NO_CONFIG = 3

CONFIG_ENV = "MANAGE_SKILL_CONFIG"
DEFAULT_CONFIG = os.path.join("~", ".config", "manage-skill", "sources.json")

PROJECT_LOCK = "skills-lock.json"
GLOBAL_LOCK = ".skill-lock.json"
STORE = os.path.join(".agents", "skills")

SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def die(msg, code=1):
    print("error: " + msg, file=sys.stderr)
    sys.exit(code)


def config_path():
    return os.path.abspath(os.path.expanduser(
        os.environ.get(CONFIG_ENV) or DEFAULT_CONFIG))


def canonical_url(url, source_type=None):
    if not url:
        return None
    u = url.strip()
    m = re.match(r"^git@([^:]+):(.+)$", u)
    if m:
        host, path = m.group(1), m.group(2)
    else:
        m = re.match(r"^[a-z+]+://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", u, re.I)
        if m:
            host, path = m.group(1), m.group(2)
        elif re.match(r"^[^/:\s]+/[^/:\s]+$", u) and source_type in (None, "github"):
            host, path = "github.com", u
        else:
            return u.rstrip("/")
    path = re.sub(r"\.git$", "", path.rstrip("/"))
    return "%s/%s" % (host.lower(), path)


def validate_config(cfg):
    problems = []
    if not isinstance(cfg, dict):
        return ["top level must be a JSON object"]
    agents = cfg.get("agents")
    if not (isinstance(agents, list) and agents
            and all(isinstance(a, str) and a for a in agents)):
        problems.append("`agents` must be a non-empty list of skills-CLI agent ids")
    dirs = cfg.get("agent_skill_dirs")
    if not (isinstance(dirs, list) and all(isinstance(d, str) and d for d in dirs)):
        problems.append("`agent_skill_dirs` must be a list of relative folders, "
                        "e.g. [\".claude/skills\"]")
    elif any(os.path.isabs(os.path.expanduser(d)) for d in dirs):
        problems.append("`agent_skill_dirs` entries must be relative: they are "
                        "resolved against the home folder (global) and the "
                        "project root (project)")
    sources = cfg.get("sources")
    if not isinstance(sources, list):
        problems.append("`sources` must be a list")
        return problems
    seen = set()
    for i, src in enumerate(sources):
        label = "sources[%d]" % i
        if not isinstance(src, dict):
            problems.append("%s must be an object" % label)
            continue
        name = src.get("name")
        if not name:
            problems.append("%s has no `name`" % label)
        elif name in seen:
            problems.append("%s: duplicate source name '%s'" % (label, name))
        seen.add(name)
        label = "source '%s'" % (name or i)
        policy = src.get("policy")
        if policy not in POLICIES:
            problems.append("%s: `policy` must be one of %s"
                            % (label, ", ".join(POLICIES)))
            continue
        if policy == EXTERNAL:
            continue
        if not src.get("url"):
            problems.append("%s: `url` is required" % label)
        if src.get("autonomy", AUTONOMY_AUTO) not in AUTONOMY:
            problems.append("%s: `autonomy` must be one of %s"
                            % (label, ", ".join(AUTONOMY)))
        if policy in EDITABLE:
            if not src.get("clone"):
                problems.append("%s: policy %s needs a `clone` path" % (label, policy))
            if not src.get("default_branch"):
                problems.append("%s: policy %s needs `default_branch`" % (label, policy))
    return problems


def load_config(path=None):
    path = path or config_path()
    try:
        with open(path, encoding="utf-8-sig") as fh:
            cfg = json.load(fh)
    except FileNotFoundError:
        print("error: no config at %s\n"
              "This is a first run. Follow SKILL.md § First run: "
              "`init_config.py --discover`, interview the user, then "
              "`init_config.py --write`." % path, file=sys.stderr)
        sys.exit(EXIT_NO_CONFIG)
    except ValueError as exc:
        die("config is not valid JSON (%s): %s" % (path, exc))
    problems = validate_config(cfg)
    if problems:
        die("config %s is invalid:\n  - %s" % (path, "\n  - ".join(problems)))
    cfg["path"] = path
    for src in cfg["sources"]:
        if src["policy"] == EXTERNAL:
            src.setdefault("skills", [src["name"]])
            src.setdefault("url", None)
            src.setdefault("clone", None)
            continue
        src.setdefault("default_branch", None)
        src.setdefault("autonomy", AUTONOMY_AUTO)
        clone = src.get("clone")
        src["clone"] = os.path.abspath(os.path.expanduser(clone)) if clone else None
        src["key"] = canonical_url(src["url"])
    return cfg


def global_lock_path():
    state = os.environ.get("XDG_STATE_HOME")
    if state:
        return os.path.join(state, "skills", GLOBAL_LOCK)
    return os.path.join(os.path.abspath(os.path.expanduser("~")), ".agents", GLOBAL_LOCK)


def scope_flag(scope):
    return "-g" if scope == "global" else ""


class Scope(object):
    def __init__(self, cfg, name, project_dir=None):
        self.name = name
        if name == "global":
            self.root = os.path.abspath(os.path.expanduser("~"))
            self.lock_path = global_lock_path()
        else:
            self.root = os.path.abspath(project_dir or os.getcwd())
            self.lock_path = os.path.join(self.root, PROJECT_LOCK)
        self.store = os.path.join(self.root, STORE)
        self.agent_dirs = [os.path.join(self.root, os.path.normpath(d))
                           for d in cfg["agent_skill_dirs"]]
        self.flag = scope_flag(name)
        self._lock = None

    @property
    def has_lock(self):
        return os.path.isfile(self.lock_path)

    @property
    def present(self):
        return self.has_lock or os.path.isdir(self.store)

    @property
    def lock(self):
        if self._lock is None:
            self._lock = {}
            if self.has_lock:
                try:
                    with open(self.lock_path, encoding="utf-8-sig") as fh:
                        self._lock = json.load(fh).get("skills", {}) or {}
                except ValueError as exc:
                    die("lock file is not valid JSON (%s): %s" % (self.lock_path, exc))
        return self._lock

    def installed_dir(self, name):
        cand = os.path.join(self.store, name)
        if os.path.isdir(cand):
            return cand
        for base in self.agent_dirs:
            path = os.path.join(base, name)
            if os.path.isdir(path) and not os.path.islink(path):
                return path
        return cand

    def links_for(self, name):
        out = []
        for base in self.agent_dirs:
            path = os.path.join(base, name)
            if os.path.islink(path) or os.path.exists(path):
                out.append(path)
        return out

    def skill_dirs(self):
        found = {}
        for base in [self.store] + self.agent_dirs:
            try:
                names = os.listdir(base)
            except OSError:
                continue
            for d in names:
                path = os.path.join(base, d)
                if d.startswith(".") or not os.path.isdir(path):
                    continue
                if base != self.store and os.path.islink(path):
                    continue
                found.setdefault(d, path)
        return found


def resolve_scopes(cfg, wanted="auto", project_dir=None):
    if wanted in SCOPES:
        return [Scope(cfg, wanted, project_dir)]
    scopes = [Scope(cfg, s, project_dir) for s in SCOPES]
    if os.path.normcase(scopes[0].root) == os.path.normcase(scopes[1].root):
        return [scopes[1]]
    return [s for s in scopes if s.present]


def add_scope_args(ap):
    ap.add_argument("--scope", choices=SCOPES + ("auto",), default="auto",
                    help="project = ./skills-lock.json, global = the home lock; "
                         "auto (default) reads every scope that exists")
    ap.add_argument("--project-dir", default=None,
                    help="project root (default: current directory)")


def git_sources(cfg):
    return [s for s in cfg["sources"] if s["policy"] != EXTERNAL]


def external_skills(cfg):
    out = {}
    for src in cfg["sources"]:
        if src["policy"] == EXTERNAL:
            for name in src["skills"]:
                out[name] = src
    return out


def classify_unlocked(cfg, scope):
    ext = external_skills(cfg)
    unlocked = sorted(d for d in scope.skill_dirs() if d not in scope.lock)
    return ([d for d in unlocked if d not in ext],
            [d for d in unlocked if d in ext])


def entry_url(entry):
    return entry.get("sourceUrl") or entry.get("source") or ""


def entry_keys(entry):
    st = entry.get("sourceType")
    keys = {canonical_url(entry.get("sourceUrl"), st),
            canonical_url(entry.get("source"), st)}
    keys.discard(None)
    return keys


def source_for_entry(cfg, entry):
    keys = entry_keys(entry)
    for src in git_sources(cfg):
        if src["key"] in keys:
            return src
    return None


def lock_entries_for(cfg, lock, src):
    return {n: e for n, e in lock.items() if source_for_entry(cfg, e) is src}


def has_clone(src):
    clone = src.get("clone")
    return bool(clone and os.path.isdir(os.path.join(clone, ".git")))


def run(cmd, timeout=180, binary=False, env=None):
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
    if binary:
        return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", "replace").strip()
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace").strip(),
            proc.stderr.decode("utf-8", "replace").strip())


def git(clone, *args, **kw):
    return run(["git", "-C", clone] + list(args), timeout=kw.get("timeout", 180))


def no_prompt_env():
    return dict(os.environ, GIT_TERMINAL_PROMPT="0")


def frontmatter_name(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        m = re.match(r"^name:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip("'\"")
    return None


def skills_at(repo, treeish):
    rc, out, err = git(repo, "-c", "core.quotepath=off", "ls-tree", "-r",
                       "--name-only", treeish)
    if rc != 0:
        raise RuntimeError("git ls-tree %s failed: %s" % (treeish, err))
    paths = []
    for path in out.splitlines():
        path = path.strip().strip('"')
        if not path.endswith("/SKILL.md"):
            continue
        folder = path[: -len("/SKILL.md")]
        if any(part in SKIP_DIRS for part in folder.split("/")):
            continue
        paths.append(path)
    names = {}
    _, out, _ = git(repo, "-c", "core.quotepath=off", "grep", "-n", "-E",
                    "^name:", treeish, "--", "*/SKILL.md")
    prefix = treeish + ":"
    for line in out.splitlines():
        if not line.startswith(prefix):
            continue
        parts = line[len(prefix):].split(":", 2)
        if len(parts) != 3 or parts[0] in names:
            continue
        m = re.match(r"^name:\s*(.+?)\s*$", parts[2])
        if m:
            names[parts[0]] = m.group(1).strip("'\"")
    out = {}
    for path in paths:
        folder = path[: -len("/SKILL.md")]
        out[names.get(path) or folder.split("/")[-1]] = path
    return out


def closest_names(name, candidates):
    norm = lambda x: x.replace("_", "-").lower()
    return sorted(c for c in candidates if norm(c) == norm(name))


def remote_head_branch(url):
    rc, out, _ = run(["git", "ls-remote", "--symref", url, "HEAD"],
                     timeout=120, env=no_prompt_env())
    if rc != 0:
        return None
    for line in out.splitlines():
        if line.startswith("ref:") and "\tHEAD" in line:
            return line.split()[1].rsplit("/", 1)[-1]
    return None


def remote_skills(src, ref=None, fetch=True):
    ref = ref or src.get("default_branch")
    if has_clone(src):
        if not ref:
            raise RuntimeError("source '%s' has a clone but no default_branch"
                               % src["name"])
        if fetch:
            git(src["clone"], "fetch", "--quiet", "origin")
        return skills_at(src["clone"], "origin/" + ref)

    if not ref:
        ref = remote_head_branch(src["url"])
        if not ref:
            raise RuntimeError("could not resolve default branch of %s" % src["url"])
        src["default_branch"] = ref
    tmp = tempfile.mkdtemp(prefix="manage-skill-")
    try:
        rc, _, err = run(["git", "clone", "--quiet", "--depth", "1", "--no-checkout",
                          "--branch", ref, src["url"], tmp],
                         timeout=300, env=no_prompt_env())
        if rc != 0:
            head = remote_head_branch(src["url"])
            if head and head != ref:
                raise RuntimeError(
                    "branch '%s' does not exist on %s; its default branch is "
                    "'%s'. Fix default_branch in the config." % (ref, src["url"], head))
            raise RuntimeError("clone of %s#%s failed: %s" % (src["url"], ref, err))
        return skills_at(tmp, "HEAD")
    finally:
        rmtree(tmp)


def clone_health(src, fetch=True):
    clone = src.get("clone")
    if not clone:
        return None
    if not has_clone(src):
        return {"error": "not a git clone: %s" % clone}
    if fetch:
        git(clone, "fetch", "--quiet", "origin")
    _, cur, _ = git(clone, "rev-parse", "--abbrev-ref", "HEAD")
    _, dirty, _ = git(clone, "status", "--porcelain")
    default = src["default_branch"]
    rc, counts, _ = git(clone, "rev-list", "--left-right", "--count",
                        "origin/%s...%s" % (default, default))
    behind = ahead = None
    if rc == 0 and counts:
        parts = counts.split()
        if len(parts) == 2:
            behind, ahead = int(parts[0]), int(parts[1])
    return {
        "clone": clone,
        "branch": cur,
        "on_default": cur == default,
        "dirty_files": len([l for l in dirty.splitlines() if l.strip()]),
        "behind": behind,
        "ahead": ahead,
    }


def resolve_in_clone(src, name, skill_path=None):
    clone = src.get("clone")
    if not clone:
        return None
    if skill_path:
        cand = os.path.normpath(os.path.join(clone, os.path.dirname(skill_path)))
        if os.path.isfile(os.path.join(cand, "SKILL.md")):
            return cand
    for dirpath, dirnames, filenames in os.walk(clone):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if "SKILL.md" not in filenames:
            continue
        if os.path.basename(dirpath) == name:
            return dirpath
        try:
            with open(os.path.join(dirpath, "SKILL.md"), encoding="utf-8-sig") as fh:
                if frontmatter_name(fh.read(4096)) == name:
                    return dirpath
        except (OSError, UnicodeDecodeError):
            pass
    return None


def export_from_clone(clone, ref, skill_path, dest):
    folder = os.path.dirname(skill_path)
    rc, data, _ = run(["git", "-C", clone, "archive", "--format=tar", ref, folder],
                      binary=True)
    if rc != 0:
        return False
    prefix = folder.strip("/") + "/"
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            rel = member.name[len(prefix):]
            if not rel or ".." in rel.split("/"):
                continue
            target = os.path.join(dest, *rel.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as fh:
                fh.write(tar.extractfile(member).read())
    return True


def walk_files(root):
    out = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f in SKIP_FILES:
                continue
            out.add(os.path.relpath(os.path.join(dirpath, f), root)
                    .replace(os.sep, "/"))
    return out


def same_content(a, b):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        da, db = fa.read(), fb.read()
    if da == db:
        return True
    if b"\0" in da or b"\0" in db:
        return False
    return da.replace(b"\r\n", b"\n") == db.replace(b"\r\n", b"\n")


def compare(installed, reference):
    a, b = walk_files(installed), walk_files(reference)
    modified = sorted(f for f in (a & b)
                      if not same_content(os.path.join(installed, f),
                                          os.path.join(reference, f)))
    return {"added": sorted(a - b), "removed": sorted(b - a), "modified": modified}


def _force_writable(func, path, _exc):
    try:
        os.chmod(path, 0o700)
        func(path)
    except OSError:
        pass


def rmtree(path):
    if os.path.islink(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path, onerror=_force_writable)


def mirror(src, dest):
    parent = os.path.dirname(dest.rstrip("/\\"))
    os.makedirs(parent, exist_ok=True)
    staging = tempfile.mkdtemp(prefix=".preview-", dir=parent)
    staged = os.path.join(staging, "skill")
    try:
        shutil.copytree(src, staged,
                        ignore=shutil.ignore_patterns(*(SKIP_DIRS | SKIP_FILES)))
        rmtree(dest)
        os.replace(staged, dest)
    finally:
        rmtree(staging)
