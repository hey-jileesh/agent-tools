---
name: transformation-spec
description: >
  Author source-to-target transformation specs for medallion/lakehouse data
  pipelines as concise, machine-readable YAML, plus a business-user HTML
  visualization generated from the same files. Use this skill whenever the
  user mentions source-to-target mappings, STTM, transformation specs, mapping
  documents, data mapping, bronze/silver/gold or medallion transformations,
  documenting ETL/ELT logic, spec'ing a pipeline for an LLM agent to build, or
  asks to document how a target table or column is derived — even if they
  don't say the word "spec". Also use it when reviewing or updating existing
  transformation specs.
---

# Transformation Spec Authoring

Produce source-to-target transformation specs that serve three audiences from
one file: engineers (reviewable, diffable), LLM agents (unambiguous,
code-generatable), and business users (auto-generated visualization). The
format works because every transformation is one of seven closed types and
every rule is literal SQL — never prose. Keep it that way: the moment a rule
says "concatenate the names nicely," the spec stops being executable.

## Workflow

### 1. Gather what the spec needs

Before writing, establish for each target table:

- Target name and layer flow (e.g. `bronze -> silver`)
- **Grain** — one row per what? This is the single most important line; every
  join and aggregate is validated against it
- Sources, join keys, and row-level filters
- Load strategy: `merge | append | full_refresh | scd2` (+ merge key)
- The business rule for every target column

If the user's description leaves any of these ambiguous, ask — do not invent
business logic. Inventing a default for a join key or a conditional mapping
produces a spec that looks authoritative but is wrong, which is worse than an
open question. If minor gaps remain after asking, write the spec and mark them
explicitly in `notes` as OPEN QUESTIONS.

### 2. Read the contract

Read `references/spec_guide.md` for the full vocabulary (the seven
transformation types, structural rules, tests) before authoring. Use
`assets/template.yaml` as the skeleton.

### 3. Author one YAML file per target table

Filename: `<layer>.<table>.yaml`. Key rules (full detail in the guide):

- Every target column appears exactly once; `source` is required on all types
  except `constant`/`system` (this is what makes lineage machine-extractable)
- Rules are ANSI SQL or the conditional shorthand `'in' -> 'out'; else X`
- Rules are self-contained — no macros, no "same as above"
- `tests.unique_combination` must match `grain`
- Put caveats, sibling-spec relationships, and rationale in `notes`

### 4. Validate

Run the bundled validator on every spec you write or edit:

```bash
python3 scripts/validate_spec.py <spec1.yaml> [spec2.yaml ...]
```

It checks YAML validity, required fields, the closed type vocabulary,
per-type required fields, load-mode rules, and grain/test consistency. Fix
errors before delivering; surface warnings to the user.

### 5. Always regenerate the visualization

Every authoring or editing run ends by rebuilding the business-user viewer
with **all** specs in the project embedded — not just the ones touched. The
viewer is generated from the specs, so regenerating on every change is what
guarantees documentation never drifts from the pipeline definition:

```bash
python3 scripts/build_viewer.py assets/spec_viewer_template.html <output_dir>/spec_viewer.html <all spec .yaml files>
```

The output is a single self-contained HTML file: tabs per spec, plain-language
rendering of each transformation type, hover-lineage from target columns back
to sources, and a paste-your-own-YAML tab.

### 6. Deliver

Deliver the spec YAML file(s) and `spec_viewer.html` together. Summarize
per table: grain, sources, load mode, column count, and any open questions —
then stop; the files speak for themselves.

## When consuming (not authoring) a spec

If asked to generate pipeline code from a spec: implement exactly what the
spec says, generate assertions from `tests`, verify every column in `columns`
is produced with no extras, and stop and ask when a rule is ambiguous. The
spec is the contract; code that "improves" on it silently is a bug.
