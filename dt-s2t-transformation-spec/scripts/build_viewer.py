#!/usr/bin/env python3
"""Build the business-user spec viewer by embedding spec YAML files into the template.

Usage: python3 build_viewer.py <template.html> <output.html> <spec1.yaml> [spec2.yaml ...]
"""
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml --break-system-packages")

START, END = "// {{SPECS_START}}", "// {{SPECS_END}}"


def js_template_escape(s):
    return s.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    template_path, output_path, spec_paths = sys.argv[1], sys.argv[2], sys.argv[3:]

    blocks = []
    for p in spec_paths:
        raw = open(p).read()
        spec = yaml.safe_load(raw)  # validates it parses
        name = spec.get("target") or p
        blocks.append(f"SPECS[{name!r}] = `\n{js_template_escape(raw)}\n`;")

    html = open(template_path).read()
    if START not in html or END not in html:
        sys.exit(f"Template missing {START} / {END} markers")
    pre, rest = html.split(START, 1)
    _, post = rest.split(END, 1)
    open(output_path, "w").write(pre + START + "\n" + "\n\n".join(blocks) + "\n" + END + post)
    print(f"Wrote {output_path} with {len(blocks)} spec(s): {[yaml.safe_load(open(p))['target'] for p in spec_paths]}")


if __name__ == "__main__":
    main()
