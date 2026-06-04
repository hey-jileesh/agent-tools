#!/usr/bin/env bash
# Install (sync) agent-tools skills into a target project.
#
# Each coding agent looks for skills in a different directory:
#   - Windsurf / GitHub Copilot  -> .agent/skills      (default)
#   - Claude Code / Cowork        -> .claude/skills
#   - Devin                       -> .cognition/skills
#
# Usage:
#   ./install.sh [--agent NAME] [--target DIR] [--skills "a b c"] [--all] [--list] [-y]
#
#   --agent   NAME   one of: agent|windsurf|copilot (->.agent/skills, default),
#                    claude|cowork (->.claude/skills), devin|cognition (->.cognition/skills)
#   --target  DIR    project root to install into (default: current directory)
#   --skills  LIST   space/comma separated skill names (default: all)
#   --all            install every available skill (the default)
#   --list           list available skills and exit
#   -y, --yes        non-interactive; accept defaults
#   -h, --help       show this help
#
# Re-running syncs: existing skills are mirrored (updated, with removed files
# pruned), so install == update.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

discover_skills() {
  local d
  for d in "$SCRIPT_DIR"/*/; do
    [ -f "${d}SKILL.md" ] && basename "$d"
  done | sort
}

usage() { sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

agent_dir() {
  case "$1" in
    claude|cowork)            echo ".claude/skills" ;;
    devin|cognition)          echo ".cognition/skills" ;;
    agent|windsurf|copilot|"") echo ".agent/skills" ;;
    *)                        echo "" ;;
  esac
}

AGENT="" ; TARGET="." ; ASSUME_YES=0
declare -a SKILLS=()
mapfile -t ALL_SKILLS < <(discover_skills)

while [ $# -gt 0 ]; do
  case "$1" in
    --agent)  AGENT="${2:-}"; shift 2 ;;
    --target) TARGET="${2:-}"; shift 2 ;;
    --skills) IFS=', ' read -r -a SKILLS <<< "${2:-}"; shift 2 ;;
    --all)    SKILLS=("${ALL_SKILLS[@]}"); shift ;;
    --list)   printf '%s\n' "${ALL_SKILLS[@]}"; exit 0 ;;
    -y|--yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

# Interactive selection when nothing was specified and we have a terminal.
if [ -z "$AGENT" ] && [ ${#SKILLS[@]} -eq 0 ] && [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ]; then
  echo "Select coding agent (skills directory):"
  echo "  1) .agent/skills      Windsurf, GitHub Copilot   [default]"
  echo "  2) .claude/skills     Claude Code, Cowork"
  echo "  3) .cognition/skills  Devin"
  printf "Choice [1]: "; read -r ch
  case "${ch:-1}" in 2) AGENT=claude ;; 3) AGENT=devin ;; *) AGENT=agent ;; esac
  echo "Available skills: ${ALL_SKILLS[*]}"
  printf "Install which? (space-separated, blank = all): "; read -r line
  [ -n "$line" ] && IFS=' ' read -r -a SKILLS <<< "$line"
fi

AGENT="${AGENT:-agent}"
SKDIR="$(agent_dir "$AGENT")"
[ -n "$SKDIR" ] || { echo "Unknown agent '$AGENT'. Use agent|claude|devin (see --help)." >&2; exit 2; }
[ ${#SKILLS[@]} -gt 0 ] || SKILLS=("${ALL_SKILLS[@]}")

TARGET_ABS="$(cd "$TARGET" 2>/dev/null && pwd || true)"
[ -n "$TARGET_ABS" ] || { echo "Target directory not found: $TARGET" >&2; exit 2; }
if [ "$TARGET_ABS" = "$SCRIPT_DIR" ]; then
  echo "Refusing to install into the agent-tools repo itself. Pass --target <project>." >&2
  exit 2
fi

DEST="$TARGET_ABS/$SKDIR"
mkdir -p "$DEST"
echo "Installing into: $DEST"

count=0
for s in "${SKILLS[@]}"; do
  src="$SCRIPT_DIR/$s"
  if [ ! -f "$src/SKILL.md" ]; then
    echo "  skip:   '$s' is not a skill (no SKILL.md)" >&2
    continue
  fi
  action="installed"; [ -e "$DEST/$s" ] && action="synced"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' "$src/" "$DEST/$s/"
  else
    rm -rf "$DEST/$s"; mkdir -p "$DEST/$s"; cp -R "$src/." "$DEST/$s/"
    find "$DEST/$s" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
  fi
  echo "  $action: $s"
  count=$((count + 1))
done

echo "Done — $count skill(s) in $SKDIR for agent '$AGENT'."
