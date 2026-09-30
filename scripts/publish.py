#!/usr/bin/env python3
"""Publishes STEP files that the Fusion script drops in ~/SeedHammer/outbox.

For each <Model>-v<n>.step: check the file, run the privacy gate, check that main matches origin/main, replace the old
version, update the README table, commit, check the remote again and push. Anything that fails moves the file to
outbox/held with a .reason file and a notification; nothing is pushed.

    publish.py                   process the outbox (what launchd runs)
    publish.py --dry-run FILE    run every check without committing
    publish.py approve FILE      approve a held file's new text and put it back in the queue
"""
import fcntl
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import step_privacy

REPO = step_privacy.ROOT
HOME = os.path.expanduser('~/SeedHammer')
OUTBOX = os.path.join(HOME, 'outbox')
HELD = os.path.join(OUTBOX, 'held')
# Model: (folder, Fusion design, README description for its first row). The models are also listed in
# ExportToOutbox.py, step_privacy.py (header name) and .github/workflows/notify-viewer.yml.
MODELS = {
    'Hammer': ('hammer', 'Hammer_V3P', 'Hammer engraving machine, complete assembly'),
    'Seed': ('seed', 'seed_v4', 'Seed controller, V4 without battery'),
    'II': ('II', 'SH2_P', 'II engraving machine, complete assembly'),
}
NAME = re.compile(rf'({"|".join(MODELS)})-v(\d+)\.step')
APPROVED = os.path.relpath(step_privacy.APPROVED, REPO)
# TZ=UTC: commit dates in UTC, like the STEP time stamp.
ENV = dict(os.environ, GIT_SSH_COMMAND='ssh -o BatchMode=yes', TZ='UTC',
           PATH='/opt/homebrew/bin:' + os.environ.get('PATH', ''))


class Hold(Exception):
    pass


def git(*args):
    done = subprocess.run(['git', '-C', REPO, *args], capture_output=True, text=True, env=ENV)
    if done.returncode:
        raise Hold(f'git {" ".join(args)} failed:\n{done.stderr.strip() or done.stdout.strip()}')
    return done.stdout.rstrip()


def notify(title, message):
    script = 'display notification item 1 of argv with title item 2 of argv'
    subprocess.run(['osascript', '-e', f'on run argv\n{script}\nend run', message, title], capture_output=True)


def log(message):
    print(message, flush=True)


def check_file(path):
    m = NAME.fullmatch(os.path.basename(path))
    if not m:
        raise Hold('The name must be ' + ' or '.join(f'{name}-v<n>.step' for name in MODELS) + '.')
    model, version = m[1], int(m[2])
    with open(path, 'rb') as f:
        f.seek(max(0, os.path.getsize(path) - 64))
        if not f.read().rstrip().endswith(b'END-ISO-10303-21;'):
            raise Hold('The file is incomplete (no END-ISO-10303-21).')
    folder = os.path.join(REPO, MODELS[model][0])
    names = os.listdir(folder) if os.path.isdir(folder) else []  # no folder yet: the model's first version
    current = [(int(n[2]), n[0]) for n in map(NAME.fullmatch, names) if n and n[1] == model]
    if current and version <= max(current)[0]:
        raise Hold(f'Version {version} is not newer than the published {max(current)[1]}.')
    return model, version, [name for _, name in current]


def to_utc(data):
    """Rewrites the header time_stamp to UTC, so the file does not say which time zone it was exported in."""
    stamp = re.compile(rb"(/\* time_stamp \*/ ')([^']*)(')")
    m = stamp.search(data, 0, 4000)
    if not m:
        raise Hold('The STEP header has no time_stamp.')
    utc = datetime.fromisoformat(m[2].decode()).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return data[:m.start(2)] + utc.encode() + data[m.end(2):]


def check_privacy(path, data):
    unknown, blocked = step_privacy.scan(data, step_privacy.load_approved())
    if blocked:
        raise Hold('Blocked text (can never be published; fix it in Fusion):\n' + '\n'.join(
            repr(step_privacy.decode(v)) for v in blocked))
    if unknown:
        raise Hold(f'{len(unknown)} strings are not approved yet. Review with: scripts/publish.py approve '
                   f'{os.path.join(HELD, os.path.basename(path))}\n' + '\n'.join(
                       repr(step_privacy.decode(v)) for v in unknown))


def check_git():
    if git('symbolic-ref', '--short', 'HEAD') != 'main':
        raise Hold('sh-hardware is not on main.')
    dirty = [line[3:] for line in git('status', '--porcelain', '--untracked-files=all').splitlines()]
    if [p for p in dirty if p != APPROVED]:
        raise Hold('sh-hardware has uncommitted changes:\n' + '\n'.join(dirty))
    git('fetch', '--quiet', 'origin')
    local, remote = git('rev-parse', 'main'), git('rev-parse', 'origin/main')
    if local != remote:
        ahead, behind = git('rev-list', '--left-right', '--count', 'main...origin/main').split()
        raise Hold(f'main does not match origin/main ({ahead} ahead, {behind} behind). Sync it first.')
    return remote


def update_readme(model, version):
    folder, doc, description = MODELS[model]
    path = os.path.join(REPO, 'README.md')
    with open(path, encoding='utf-8') as f:
        text = f.read()
    row = re.compile(rf'^(\| `{folder}/{model}-v)\d+(\.step` \|.*\| Fusion `{doc}`, version )\d+( \|)$', re.M)
    text, count = row.subn(rf'\g<1>{version}\g<2>{version}\g<3>', text)
    if count == 0 and f'`{folder}/{model}-v' not in text:
        # The model's first version: add its row after the last one of the table.
        rows = list(re.finditer(r'^\| `[^`]+-v\d+\.step` \|.*\|$', text, re.M))
        if rows:
            end = rows[-1].end()
            new_row = f'| `{folder}/{model}-v{version}.step` | {description} | Fusion `{doc}`, version {version} |'
            text = f'{text[:end]}\n{new_row}{text[end:]}'
            count = 1
    if count != 1:
        raise Hold(f'Could not find the {model} row in the README table.')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def publish(path, dry_run=False):
    model, version, old = check_file(path)
    with open(path, 'rb') as f:
        data = to_utc(f.read())
    check_privacy(path, data)
    remote = check_git()
    if dry_run:
        return f'{os.path.basename(path)} passes every check (dry run, nothing committed).'
    folder = MODELS[model][0]
    new = f'{folder}/{os.path.basename(path)}'
    new_folder = not os.path.isdir(os.path.join(REPO, folder))
    try:
        for name in old:
            git('rm', '--quiet', f'{folder}/{name}')
        os.makedirs(os.path.join(REPO, folder), exist_ok=True)  # git rm removes the folder once it is empty
        with open(os.path.join(REPO, new), 'wb') as f:
            f.write(data)
        update_readme(model, version)
        git('add', new, 'README.md', APPROVED)
        git('commit', '--quiet', '-s', '-m', f'Export the {model} at version {version}', '-m',
            f'Exported from the saved Fusion design {MODELS[model][1]} and published by scripts/publish.py.')
    except Exception:
        # Undo only what this run changed; approvals not yet committed stay in the working tree.
        git('reset', '--quiet')
        git('checkout', 'HEAD', '--', 'README.md', *(f'{folder}/{name}' for name in old))
        if os.path.exists(os.path.join(REPO, new)):
            os.remove(os.path.join(REPO, new))
        folder_path = os.path.join(REPO, folder)
        if new_folder and os.path.isdir(folder_path) and not os.listdir(folder_path):
            os.rmdir(folder_path)  # this run created it
        raise
    os.remove(path)
    commit = git('rev-parse', '--short', 'HEAD')
    git('fetch', '--quiet', 'origin')
    if git('rev-parse', 'origin/main') != remote:
        raise Hold(f'origin/main moved while committing; {commit} is committed locally but not pushed.')
    git('push', '--quiet', 'origin', 'main')
    return f'Published {model}-v{version} ({commit}).'


def hold(path, reason):
    os.makedirs(HELD, exist_ok=True)
    target = os.path.join(HELD, os.path.basename(path))
    if os.path.exists(path):
        os.replace(path, target)
    with open(target + '.reason', 'w', encoding='utf-8') as f:
        f.write(reason + '\n')
    log(f'held {os.path.basename(path)}: {reason}')
    notify('SeedHammer: not published', f'{os.path.basename(path)}: {reason.splitlines()[0]}')


def run_outbox():
    os.makedirs(OUTBOX, exist_ok=True)
    with open(os.path.join(HOME, '.lock'), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        while True:
            queue = sorted(p for p in os.listdir(OUTBOX) if p.endswith('.step'))
            if not queue:
                return 0
            path = os.path.join(OUTBOX, queue[0])
            try:
                message = publish(path)
            except Hold as e:
                hold(path, str(e))
                continue
            except Exception as e:  # anything unexpected still must not leave the file in the queue forever
                hold(path, f'Unexpected error: {e!r}')
                continue
            log(message)
            notify('SeedHammer: published', message)


def approve(path):
    if step_privacy.main(['step_privacy.py', 'approve', path]):
        return 1
    publish(path, dry_run=True)  # raises Hold if anything else is still wrong
    os.replace(path, os.path.join(OUTBOX, os.path.basename(path)))
    if os.path.exists(path + '.reason'):
        os.remove(path + '.reason')
    print('Back in the outbox. Run scripts/publish.py to publish it.')
    return 0


def main(argv):
    try:
        if len(argv) == 1:
            return run_outbox()
        if len(argv) == 3 and argv[1] == '--dry-run':
            print(publish(argv[2], dry_run=True))
            return 0
        if len(argv) == 3 and argv[1] == 'approve':
            return approve(argv[2])
    except Hold as e:
        print(f'not published: {e}', file=sys.stderr)
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
