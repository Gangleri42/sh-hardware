#!/bin/sh
# Blocks commits that leak local paths, email addresses, or Autodesk document ids.
# Checks staged text files, plus the header of staged STEP files.
set -eu

pattern='/Users/|/home/[a-z]|C:\\Users|urn:adsk|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
allow='noreply@|@users.noreply.github.com|git@github.com'

fail=0
for f in $(git diff --cached --name-only --diff-filter=ACM); do
	case "$f" in
		LICENSE|scripts/privacy-check.sh) continue ;;
		*.step|*.stp) content=$(git show ":$f" | head -40) ;;
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
