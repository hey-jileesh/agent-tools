#!/usr/bin/env python3
"""Software Composition Analysis (SCA) documentation generator.

Detects a repo's ecosystem, runs the native dependency-tree command, and renders a
**self-contained, searchable, collapsible HTML tree** of the full dependency graph —
so you can answer questions like "is log4j 1.2 anywhere in here?" by typing it into a
search box. It also flags **version conflicts** (the same library resolved at multiple
versions), which is the bread and butter of composition analysis.

Supported ecosystems:
    java   -> mvn dependency:tree                 (Maven)
    node   -> npm ls --all --json                 (npm; works for yarn/pnpm installs too)
    python -> pipdeptree --json-tree              (reflects the INSTALLED environment)

Usage:
    # auto-detect ecosystem, run the command in the repo, write <repo>/SCA.html
    python3 generate_sca.py <repo-path>

    # force the ecosystem and/or output path
    python3 generate_sca.py <repo-path> --type java --out report.html

    # parse a dependency tree you already captured (no toolchain needed) — handy for
    # CI logs, testing, or when deps were resolved in a separate step
    python3 generate_sca.py <repo-path> --type java --from-file deptree.txt

The HTML itself is fully standalone (inline CSS + JS, no network, no build step).
This script needs only the Python standard library; running the live commands needs
the ecosystem's own toolchain present (mvn / npm / pipdeptree), with dependencies
already resolved (e.g. `npm install`, `pip install -r requirements.txt`) for an
accurate, complete tree.
"""
import argparse
import html
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

MAX_DEPTH = 200          # guard against pathological/cyclic dependency trees
MAX_INPUT_BYTES = 50 * 1024 * 1024  # cap how much command/file output we parse


# --- ecosystem detection ---------------------------------------------------

def detect_type(root):
    if (root / "pom.xml").exists():
        return "java"
    if (root / "package.json").exists():
        return "node"
    if any((root / m).exists() for m in
           ("requirements.txt", "pyproject.toml", "Pipfile", "setup.py")):
        return "python"
    return None


# --- running the native commands -------------------------------------------

def run(cmd, cwd):
    try:
        return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    except FileNotFoundError:
        return None


def gather_raw(dep_type, root):
    """Run the ecosystem's dependency-tree command and return its raw output text."""
    if dep_type == "java":
        res = run(["mvn", "-B", "dependency:tree"], root)
        if res is None:
            die("`mvn` not found on PATH. Install Maven or pass --from-file.")
        if res.returncode != 0 and "BUILD SUCCESS" not in res.stdout:
            die("mvn dependency:tree failed:\n" + (res.stderr or res.stdout)[-1500:])
        return res.stdout
    if dep_type == "node":
        res = run(["npm", "ls", "--all", "--json"], root)
        if res is None:
            die("`npm` not found on PATH. Install Node/npm or pass --from-file.")
        # npm ls exits non-zero on extraneous/peer issues but still prints valid JSON
        return res.stdout
    if dep_type == "python":
        for cmd in (["pipdeptree", "--json-tree"],
                    ["python3", "-m", "pipdeptree", "--json-tree"]):
            res = run(cmd, root)
            if res is not None and res.returncode == 0 and res.stdout.strip():
                return res.stdout
        die("pipdeptree not available. `pip install pipdeptree` (and install the "
            "project's deps first), or pass --from-file.")
    die(f"Unknown ecosystem: {dep_type}")


# --- parsers: each returns a common node {name, version, label, children} ---

def _node(name, version, label=None, scope=""):
    lbl = label if label is not None else (f"{name} {version}".strip())
    return {"name": name, "version": version, "label": lbl,
            "scope": scope, "children": []}


def parse_java(text):
    """Parse `mvn dependency:tree` text output into a tree (supports multi-module)."""
    coord_re = re.compile(r"^[\w.\-]+:[\w.\-]+:")
    synth = _node("(project)", "", "(project)")
    stack = [(-1, synth)]
    for line in text.splitlines():
        m = re.match(r"^\[INFO\]\s(.*)$", line)
        if not m:
            continue
        rest = m.group(1)
        idx = rest.find("+- ")
        if idx == -1:
            idx = rest.find("\\- ")
        if idx == -1:
            coord = rest.strip()
            depth = 0
        else:
            coord = rest[idx + 3:].strip()
            depth = len(rest[:idx]) // 3 + 1
        coord = coord.split(" ")[0]          # drop annotations like "(optional)"
        if not coord_re.match(coord):
            continue
        parts = coord.split(":")
        scope = ""
        if len(parts) == 4:
            g, a, _pkg, ver = parts
        elif len(parts) == 5:
            g, a, _pkg, ver, scope = parts
        elif len(parts) >= 6:
            g, a, _pkg = parts[0], parts[1], parts[2]
            ver, scope = parts[4], parts[5]
        else:
            continue
        name = f"{g}:{a}"
        label = f"{name}:{ver}" + (f"  [{scope}]" if scope else "")
        node = _node(name, ver, label, scope)
        while stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1]["children"].append(node)
        stack.append((depth, node))
    # collapse the synthetic root if there's a single real root (single-module build)
    if len(synth["children"]) == 1:
        return synth["children"][0]
    return synth


def parse_node(text):
    data = json.loads(text)

    def walk(name, obj, depth, seen):
        ver = obj.get("version", "")
        node = _node(name, ver, f"{name}@{ver}" if ver else name)
        key = f"{name}@{ver}"
        # stop on cycles (npm trees can be circular) or pathological depth
        if depth >= MAX_DEPTH or key in seen:
            return node
        seen = seen | {key}
        for dn, dobj in (obj.get("dependencies") or {}).items():
            if isinstance(dobj, dict):
                node["children"].append(walk(dn, dobj, depth + 1, seen))
        return node

    return walk(data.get("name", "(root)"), data, 0, frozenset())


def parse_python(text):
    arr = json.loads(text)

    def walk(obj, depth, seen):
        name = obj.get("package_name") or obj.get("key") or "?"
        ver = obj.get("installed_version") or obj.get("version") or ""
        node = _node(name, ver, f"{name}=={ver}" if ver else name)
        key = f"{name}=={ver}"
        if depth >= MAX_DEPTH or key in seen:
            return node
        seen = seen | {key}
        for c in (obj.get("dependencies") or []):
            node["children"].append(walk(c, depth + 1, seen))
        return node

    synth = _node("(environment)", "", "(installed packages)")
    synth["children"] = [walk(o, 0, frozenset()) for o in arr]
    return synth


PARSERS = {"java": parse_java, "node": parse_node, "python": parse_python}


# --- analysis --------------------------------------------------------------

def analyze(root):
    versions = {}     # name -> set(version)
    total = 0
    # iterative DFS so deep trees can't hit the recursion limit
    stack = [(root, True)]
    while stack:
        n, is_root = stack.pop()
        if not is_root and n["name"] and not n["name"].startswith("("):
            total += 1
            versions.setdefault(n["name"], set()).add(n["version"])
        for c in n["children"]:
            stack.append((c, False))
    conflicts = {name: sorted(v) for name, v in versions.items() if len(v) > 1}
    return {"total_nodes": total, "unique": len(versions),
            "conflicts": conflicts}


# --- HTML rendering --------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  /* Brand-neutral design tokens, inlined because the report is a standalone file.
     Swap these values to match your own palette/typography if desired. */
  :root {
    color-scheme: light;
    --brand-navy:#1A3673; --brand-medium-navy:#2861BB; --brand-light-navy:#6A97DF;
    --brand-pale-navy:#E1EDFF; --brand-cyan:#44B8F3; --brand-light-cyan:#C7EAFB;
    --brand-pale-cyan:#E3F4FD; --brand-terra-cotta:#E3725F; --brand-turquoise:#00BBBA;
    --brand-dark-gray:#231E33;
    --background:#ffffff; --foreground:#231E33;
    --card:#ffffff; --card-foreground:#231E33;
    --primary:#1A3673; --primary-foreground:#ffffff;
    --accent:#44B8F3; --accent-foreground:#1A3673;
    --muted:#E1EDFF; --muted-foreground:#666666;
    --destructive:#E3725F;
    --border:#D9D9D9; --ring:#44B8F3;
    --elevation-sm:0px 2px 4px rgba(0,0,0,0.05);
    --radius:12px; --radius-sm:8px; --radius-lg:16px;
    --font-size:16px;
    --text-h3:36px; --text-h4:28px; --text-p:18px; --text-label:14px;
    --font-weight-regular:400; --font-weight-medium:500; --font-weight-semibold:600;
  }
  * { box-sizing: border-box; }
  html { font-size: var(--font-size); }
  /* The report stays on a light theme with a white page background. */
  body { font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-weight: var(--font-weight-regular);
         font-size: var(--text-label); line-height: 1.5; margin: 0;
         background: var(--background); color: var(--foreground); }
  header { position: sticky; top: 0; z-index: 5; background: var(--card);
           border-bottom: 1px solid var(--border); padding: 1.25rem 1.5rem; }
  h1 { font-size: var(--text-h3); line-height: 1.2; margin: 0 0 .25rem;
       font-weight: var(--font-weight-semibold); color: var(--primary); }
  .sub { color: var(--muted-foreground); font-size: var(--text-label); }
  .stats { display: flex; gap: 1.5rem; margin-top: .75rem; flex-wrap: wrap;
           font-size: var(--text-label); color: var(--muted-foreground); }
  .stats .num { font-size: var(--text-h4); font-weight: var(--font-weight-semibold);
                color: var(--primary); line-height: 1.2; margin-right: .35rem;
                font-variant-numeric: tabular-nums; }
  .stats .num.warn { color: var(--destructive); }
  .controls { display: flex; gap: .5rem; margin-top: .85rem; flex-wrap: wrap; align-items: center; }
  input[type=search] { flex: 1; min-width: 240px; padding: .55rem .7rem; font: inherit;
           color: var(--foreground); background: var(--card); border: 1px solid var(--border);
           border-radius: var(--radius-sm); }
  input[type=search]:focus { outline: 2px solid var(--ring); outline-offset: 1px;
           border-color: var(--ring); }
  button { font: inherit; padding: .5rem .8rem; color: var(--primary); background: var(--card);
           border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer; }
  button:hover { border-color: var(--primary); }
  label.chk { font-size: var(--text-label); color: var(--muted-foreground);
              display: flex; gap: .35rem; align-items: center; }
  #count { font-size: var(--text-label); color: var(--muted-foreground); }
  main { padding: 1.25rem 1.5rem 4rem; }
  .panel { background: var(--card); border: 1px solid var(--border);
           border-left: 5px solid var(--destructive); border-radius: var(--radius);
           box-shadow: var(--elevation-sm); padding: .85rem 1rem; margin-bottom: 1rem; }
  .panel h2 { font-size: var(--text-label); margin: 0 0 .5rem; text-transform: uppercase;
              letter-spacing: .04em; font-weight: var(--font-weight-semibold);
              color: var(--muted-foreground); }
  #tree { background: var(--card); border: 1px solid var(--border);
          border-left: 5px solid var(--primary); border-radius: var(--radius);
          box-shadow: var(--elevation-sm); padding: .85rem 1rem; }
  ul { list-style: none; margin: 0; padding-left: 1.1rem; }
  ul.root { padding-left: 0; }
  .node { display: flex; align-items: baseline; gap: .4rem; padding: .12rem .4rem;
          border-radius: var(--radius-sm); font-variant-numeric: tabular-nums; }
  .node:hover { background: color-mix(in srgb, var(--primary) 6%, transparent); }
  .tog { width: 1rem; display: inline-block; cursor: pointer; text-align: center;
         color: var(--muted-foreground); user-select: none; }
  li:not(.leaf) > .node > .tog::before { content: "-"; }
  li.collapsed:not(.leaf) > .node > .tog::before { content: "+"; }
  .lbl { font-size: var(--text-label); }
  li.collapsed > ul { display: none; }
  li.hidden { display: none; }
  mark { background: var(--brand-light-cyan); color: var(--brand-navy);
         padding: 0 1px; border-radius: 3px; font-weight: var(--font-weight-medium); }
  .matchrow > .node { background: color-mix(in srgb, var(--accent) 14%, transparent); }
  .conflict { display: inline-block; cursor: pointer; margin: .2rem .35rem .2rem 0;
              padding: .25rem .55rem; font-size: var(--text-label); color: var(--foreground);
              border-radius: var(--radius-sm);
              background: color-mix(in srgb, var(--destructive) 12%, transparent);
              border: 1px solid color-mix(in srgb, var(--destructive) 35%, transparent); }
  .conflict:hover { border-color: var(--destructive); }
  .empty { color: var(--muted-foreground); }
</style></head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="sub">__SUBTITLE__</div>
  <div class="stats">
    <span><span class="num" id="s-total">0</span>dependency edges</span>
    <span><span class="num" id="s-unique">0</span>unique libraries</span>
    <span><span class="num warn" id="s-conf">0</span>version conflicts</span>
  </div>
  <div class="controls">
    <input type="search" id="q" placeholder="Search e.g. log4j 1.2  (space = AND across name &amp; version)" autocomplete="off">
    <button id="expand">Expand all</button>
    <button id="collapse">Collapse all</button>
    <label class="chk"><input type="checkbox" id="only"> only matches</label>
    <span id="count"></span>
  </div>
</header>
<main>
  <div class="panel" id="conf-panel" style="display:none">
    <h2>Version conflicts (same library, multiple versions)</h2>
    <div id="conflicts"></div>
  </div>
  <div id="tree"></div>
</main>
<script>
const TREE = __TREE__;
const META = __META__;

document.getElementById('s-total').textContent = META.total_nodes;
document.getElementById('s-unique').textContent = META.unique;
const confNames = Object.keys(META.conflicts);
document.getElementById('s-conf').textContent = confNames.length;

// conflicts panel
if (confNames.length) {
  document.getElementById('conf-panel').style.display = '';
  const box = document.getElementById('conflicts');
  confNames.sort().forEach(n => {
    const el = document.createElement('span');
    el.className = 'conflict';
    el.textContent = n + '  →  ' + META.conflicts[n].join(', ');
    el.title = 'Click to search for ' + n;
    el.onclick = () => { q.value = n; runSearch(); };
    box.appendChild(el);
  });
}

// build tree DOM
function build(node, isRoot) {
  const li = document.createElement('li');
  const hasKids = node.children && node.children.length;
  if (!hasKids) li.className = 'leaf';
  const row = document.createElement('div');
  row.className = 'node';
  const tog = document.createElement('span');
  tog.className = 'tog';  // +/- affordance is supplied via CSS ::before
  tog.onclick = () => li.classList.toggle('collapsed');
  const lbl = document.createElement('span');
  lbl.className = 'lbl';
  lbl.textContent = node.label;
  lbl.dataset.search = (node.label || '').toLowerCase();
  row.appendChild(tog); row.appendChild(lbl);
  li.appendChild(row);
  if (hasKids) {
    const ul = document.createElement('ul');
    node.children.forEach(c => ul.appendChild(build(c, false)));
    li.appendChild(ul);
  }
  return li;
}
const rootUl = document.createElement('ul');
rootUl.className = 'root';
rootUl.appendChild(build(TREE, true));
document.getElementById('tree').appendChild(rootUl);

const q = document.getElementById('q');
const only = document.getElementById('only');
const countEl = document.getElementById('count');

// HTML-escape, so a dependency name containing markup is rendered as text, not DOM.
function esc(s) {
  return s.replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
// Build a highlighted, fully-escaped label: every segment is esc()'d; only the
// <mark> tags we add ourselves are real markup.
function highlight(text, tokens) {
  const lower = text.toLowerCase();
  let ranges = [];
  tokens.forEach(t => { let i = lower.indexOf(t);
    while (i >= 0) { ranges.push([i, i + t.length]); i = lower.indexOf(t, i + t.length); } });
  if (!ranges.length) return esc(text);
  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [ranges[0]];
  for (let k = 1; k < ranges.length; k++) {
    const last = merged[merged.length - 1];
    if (ranges[k][0] <= last[1]) last[1] = Math.max(last[1], ranges[k][1]);
    else merged.push(ranges[k]);
  }
  let out = '', pos = 0;
  merged.forEach(([s, e]) => {
    out += esc(text.slice(pos, s)) + '<mark>' + esc(text.slice(s, e)) + '</mark>';
    pos = e;
  });
  return out + esc(text.slice(pos));
}
function runSearch() {
  const tokens = q.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);
  const allLi = document.querySelectorAll('#tree li');
  allLi.forEach(li => li.classList.remove('hidden','matchrow'));
  if (!tokens.length) {
    // setting textContent clears any <mark> children safely (no HTML parsing)
    document.querySelectorAll('#tree .lbl').forEach(l => { l.textContent = l.textContent; });
    countEl.textContent = '';
    return;
  }
  let matches = 0;
  allLi.forEach(li => {
    const lbl = li.querySelector(':scope > .node > .lbl');
    const text = lbl.textContent;
    const hit = tokens.every(t => text.toLowerCase().includes(t));
    if (hit) {
      matches++;
      li.classList.add('matchrow');
      lbl.innerHTML = highlight(text, tokens);
      let p = li.parentElement;
      while (p && p.id !== 'tree') {
        if (p.tagName === 'LI') p.classList.remove('collapsed','hidden');
        p = p.parentElement;
      }
    } else {
      lbl.textContent = text;
    }
  });
  if (only.checked) {
    // hide branches with no match in their subtree
    const keep = new Set();
    document.querySelectorAll('#tree li.matchrow').forEach(li => {
      let p = li;
      while (p && p.id !== 'tree') { if (p.tagName==='LI') keep.add(p); p = p.parentElement; }
      li.querySelectorAll('li').forEach(d => keep.add(d)); // keep descendants of a match
    });
    allLi.forEach(li => { if (!keep.has(li)) li.classList.add('hidden'); });
  }
  countEl.textContent = matches + ' match' + (matches===1?'':'es');
}
q.addEventListener('input', runSearch);
only.addEventListener('change', runSearch);
document.getElementById('expand').onclick = () =>
  document.querySelectorAll('#tree li').forEach(li => li.classList.remove('collapsed'));
document.getElementById('collapse').onclick = () =>
  document.querySelectorAll('#tree li').forEach(li => {
    if (li.querySelector(':scope > ul')) li.classList.add('collapsed');
  });
</script>
</body></html>
"""


def _js(obj):
    """Serialize to JSON safe to embed inside an inline <script>. json.dumps does not
    escape `</script>`, `<`, `>` or `&`, so a dependency name containing markup could
    otherwise break out of the script context and execute (XSS). ensure_ascii=True
    already escapes U+2028/2029 and all other non-ASCII."""
    return (json.dumps(obj)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def render_html(tree, meta, title, subtitle):
    # single-pass substitution: replacement values are never re-scanned, so data that
    # happens to contain another placeholder token can't cause injection.
    repl = {"__TITLE__": html.escape(title), "__SUBTITLE__": html.escape(subtitle),
            "__TREE__": _js(tree), "__META__": _js(meta)}
    return re.sub(r"__(?:TITLE|SUBTITLE|TREE|META)__",
                  lambda m: repl[m.group(0)], HTML_TEMPLATE)


# --- cli -------------------------------------------------------------------

def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def main(argv):
    ap = argparse.ArgumentParser(description="Generate a searchable SCA dependency-tree HTML report.")
    ap.add_argument("repo", help="path to the repository")
    ap.add_argument("--type", choices=["java", "node", "python"],
                    help="ecosystem (auto-detected if omitted)")
    ap.add_argument("--from-file", help="parse a pre-captured dependency-tree output instead of running the command")
    ap.add_argument("--out", help="output HTML path (default <repo>/SCA.html)")
    args = ap.parse_args(argv[1:])

    root = Path(args.repo).expanduser().resolve()
    if not root.exists():
        die(f"Path does not exist: {root}")

    dep_type = args.type or detect_type(root)
    if not dep_type:
        die("Could not detect ecosystem (no pom.xml / package.json / requirements). "
            "Pass --type java|node|python.")

    if args.from_file:
        raw = Path(args.from_file).read_text(encoding="utf-8", errors="replace")
    else:
        raw = gather_raw(dep_type, root)
    if raw and len(raw) > MAX_INPUT_BYTES:      # guard against pathological output
        die(f"Dependency-tree output exceeds {MAX_INPUT_BYTES} bytes; refusing to parse.")

    try:
        tree = PARSERS[dep_type](raw)
    except Exception as e:
        die(f"Failed to parse {dep_type} dependency tree: {e}")

    meta = analyze(tree)
    meta["type"] = dep_type
    title = f"Software Composition Analysis — {root.name}"
    tool = {"java": "mvn dependency:tree", "node": "npm ls --all",
            "python": "pipdeptree"}[dep_type]
    subtitle = (f"{dep_type} · source: {tool} · generated {date.today().isoformat()} "
                f"· {meta['total_nodes']} edges, {meta['unique']} unique libraries")

    out = Path(args.out) if args.out else (root / "SCA.html")
    out.write_text(render_html(tree, meta, title, subtitle), encoding="utf-8")
    print(json.dumps({"type": dep_type, "out": str(out),
                      "total_nodes": meta["total_nodes"], "unique": meta["unique"],
                      "conflicts": list(meta["conflicts"].keys())}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
