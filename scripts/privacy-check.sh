#!/bin/sh
# Blocks commits that leak local paths, email addresses, or Autodesk document ids.
# Checks staged text files; staged STEP files go through scripts/step_privacy.py, which checks all of their text.
set -eu

pattern='/Users/|/home/[a-z]|C:\\Users|urn:adsk|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
allow='noreply@|@users.noreply.github.com|git@github.com'

fail=0
for f in $(git diff --cached --name-only --diff-filter=ACM); do
	case "$f" in
		LICENSE|scripts/privacy-check.sh|scripts/step_privacy.py) continue ;;
		*.step|*.stp)
			git show ":$f" | python3 scripts/step_privacy.py check - || fail=1
			continue ;;
		*.zip|*.png|*.jpg|*.webp|*.ico|*.bin) continue ;;
		*) content=$(git show ":$f") ;;
	esac
	hits=$(printf '%s\n' "$content" | grep -nE "$pattern" | grep -vE "$allow" || true)
	if [ -n "$hits" ]; then
		printf 'privacy-check: %s\n%s\n' "$f" "$hits" >&2
		fail=1
	fi
done
exit $fail
