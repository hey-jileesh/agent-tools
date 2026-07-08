#!/usr/bin/env python3
"""Validate transformation spec YAML files against the spec contract.

Usage: python3 validate_spec.py <spec1.yaml> [spec2.yaml ...]
Exit code 0 = all specs valid (warnings allowed), 1 = errors found.
"""
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml --break-system-packages")

TYPES = {
    "direct":      {"required": ["source"]},
    "expression":  {"required": ["source", "rule"]},
    "conditional": {"required": ["source", "rule"]},
    "aggregate":   {"required": ["source", "rule"]},
    "lookup":      {"required": ["source", "lookup"]},
    "constant":    {"required": ["rule"]},
    "system":      {"required": ["rule"]},
}
LOAD_MODES = {"merge", "append", "full_refresh", "scd2"}
TOP_REQUIRED = ["target", "layer", "grain", "sources", "load", "columns"]
PROSE_HINTS = [" the ", " should ", " nicely", " appropriate", " properly"]


def validate(path):
    errors, warnings = [], []
    try:
        spec = yaml.safe_load(open(path))
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"], []
    if not isinstance(spec, dict):
        return ["Spec is not a YAML mapping"], []

    for f in TOP_REQUIRED:
        if f not in spec:
            errors.append(f"Missing required top-level field: {f}")
    if errors:
        return errors, warnings

    load = spec.get("load") or {}
    mode = load.get("mode")
    if mode not in LOAD_MODES:
        errors.append(f"load.mode '{mode}' not in {sorted(LOAD_MODES)}")
    if mode in ("merge", "scd2") and not load.get("merge_key"):
        errors.append(f"load.mode '{mode}' requires load.merge_key")

    cols = spec.get("columns") or {}
    if not isinstance(cols, dict) or not cols:
        errors.append("columns must be a non-empty mapping")
        return errors, warnings

    aliases = set((spec.get("sources") or {}).keys())
    for name, col in cols.items():
        if not isinstance(col, dict):
            errors.append(f"column '{name}': must be a mapping")
            continue
        t = col.get("type")
        if t not in TYPES:
            errors.append(f"column '{name}': type '{t}' not in closed vocabulary {sorted(TYPES)}")
            continue
        for req in TYPES[t]["required"]:
            if req not in col:
                errors.append(f"column '{name}' (type {t}): missing required field '{req}'")
        if t == "lookup":
            lk = col.get("lookup") or {}
            for k in ("table", "key", "return"):
                if k not in lk:
                    errors.append(f"column '{name}': lookup missing '{k}'")
        if t == "conditional" and "rule" in col and "else" not in str(col["rule"]).lower():
            warnings.append(f"column '{name}': conditional rule has no 'else' branch")
        rule = str(col.get("rule", ""))
        if t in ("expression", "aggregate") and any(h in rule.lower() for h in PROSE_HINTS):
            warnings.append(f"column '{name}': rule looks like prose, not SQL: {rule[:60]!r}")
        # lineage check: source aliases must be declared (skip derived-column refs)
        src = col.get("source")
        if src is not None:
            srcs = src if isinstance(src, list) else [src]
            for s in srcs:
                s = str(s)
                if "." in s:
                    head = s.split(".")[0]
                    if head not in aliases and t != "aggregate" and head not in ("bronze", "silver", "gold"):
                        warnings.append(f"column '{name}': source alias '{head}' not in sources")

    # grain vs unique_combination
    uniq = None
    for t in spec.get("tests") or []:
        if isinstance(t, dict) and "unique_combination" in t:
            uniq = t["unique_combination"]
    if uniq is None:
        warnings.append("no unique_combination test — grain claim is not machine-checked")
    else:
        missing = [c for c in uniq if c not in cols]
        if missing:
            errors.append(f"unique_combination references undefined columns: {missing}")
        grain = str(spec.get("grain", "")).lower()
        for c in uniq:
            if c.lower() not in grain:
                warnings.append(f"unique_combination column '{c}' not mentioned in grain text")

    return errors, warnings


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    failed = False
    for path in sys.argv[1:]:
        errors, warnings = validate(path)
        status = "FAIL" if errors else "OK"
        print(f"[{status}] {path}")
        for e in errors:
            print(f"  ERROR: {e}")
        for w in warnings:
            print(f"  warn:  {w}")
        failed = failed or bool(errors)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
