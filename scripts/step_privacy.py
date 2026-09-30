#!/usr/bin/env python3
"""Privacy gate for STEP files: every piece of text in the file must be approved.

A STEP file carries text in two places: string literals (names, descriptions, materials, the header) and comments.
Each one must either match a generated pattern (colours, Fusion import stamps, numbers) or be listed in
privacy/approved-strings.txt, after Fusion's instance suffixes (" (1)", ":3") are removed. The blocklist below runs over
all of it as well, so an approved string can never be a path, an Autodesk id or an address.

    step_privacy.py check FILE|-     exit 1 and list what is not approved
    step_privacy.py approve FILE     add the unknown text of FILE to the list, after asking
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPROVED = os.path.join(ROOT, 'privacy', 'approved-strings.txt')

# Same as scripts/privacy-check.sh, plus any drive path, URL or Fusion file name.
BLOCK = re.compile(
    r'/Users/|/home/[a-z]|[A-Za-z]:\\|urn:adsk|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|'
    r'nsec1[02-9ac-hj-np-z]{58}|nbunksec1[02-9ac-hj-np-z]{20,}|https?:|file:|\.f3[dz]\b|'
    r'\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d)?[+-]\d\d',  # a time stamp with a local offset gives the time zone away
    re.I,
)
GENERATED = [
    re.compile(r'[-+0-9. ,;]*'),  # empty, numbers
    re.compile(r'Opaque\(\d{1,3},\d{1,3},\d{1,3}\)'),  # colour names
    re.compile(r'\d{4}-\d\d-\d\d-\d\d-\d\d-\d\d-\d{3}(_\d+)?'),  # names Fusion gives imported bodies
    re.compile(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ'),  # header time_stamp, UTC only (publish.py rewrites it)
    re.compile(r'(Hammer|Seed|II)-v\d+\.step'),  # header name
]
SUFFIX = re.compile(r'(:\d+| \(\d+\))$')


def tokens(text):
    """Yields ('string', value) and ('comment', value) for all text in a STEP file, strings still STEP-encoded."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "'":
            out = []
            i += 1
            while True:
                if i >= n:
                    raise ValueError('unterminated string')
                if text[i] == "'":
                    if i + 1 < n and text[i + 1] == "'":
                        out.append("'")
                        i += 2
                        continue
                    break
                if text[i] not in '\r\n':  # line breaks inside a string are not part of it
                    out.append(text[i])
                i += 1
            yield 'string', ''.join(out)
        elif c == '"':
            j = text.index('"', i + 1)
            yield 'string', text[i + 1:j]
            i = j
        elif text.startswith('/*', i):
            j = text.index('*/', i + 2)
            yield 'comment', '/* ' + ' '.join(text[i + 2:j].split()) + ' */'
            i = j + 1
        i += 1


def decode(value):
    """STEP control directives (\\X\\, \\X2\\, \\S\\) to text, for the blocklist and for reading."""
    value = re.sub(r'\\X2\\((?:[0-9A-F]{4})+)\\X0\\', lambda m: bytes.fromhex(m[1]).decode('utf-16-be'), value)
    value = re.sub(r'\\X4\\((?:[0-9A-F]{8})+)\\X0\\', lambda m: bytes.fromhex(m[1]).decode('utf-32-be'), value)
    value = re.sub(r'\\X\\([0-9A-F]{2})', lambda m: bytes.fromhex(m[1]).decode('latin-1'), value)
    value = re.sub(r'\\S\\(.)', lambda m: chr(ord(m[1]) + 128), value)
    return re.sub(r'\\P.\\', '', value).replace('\\\\', '\\')


def normal(value):
    while SUFFIX.search(value):
        value = SUFFIX.sub('', value)
    return value


def load_approved(path=APPROVED):
    try:
        with open(path, encoding='utf-8') as f:
            return {line.rstrip('\n') for line in f if line.strip()}
    except FileNotFoundError:
        return set()


def scan(data, approved):
    """Returns (unknown, blocked): text not on the list, and text the blocklist matches."""
    text = data.decode('latin-1')
    unknown, blocked = set(), set()
    for kind, value in tokens(text):
        plain = decode(value)
        if BLOCK.search(plain) or BLOCK.search(value):
            blocked.add(plain)
        elif kind == 'comment':
            if value not in approved:
                unknown.add(value)
        elif not any(p.fullmatch(plain) for p in GENERATED) and normal(value) not in approved:
            unknown.add(normal(value))
    # Also outside strings and comments, in case the tokenizer is ever wrong.
    for m in BLOCK.finditer(text):
        blocked.add(m[0])
    return sorted(unknown), sorted(blocked)


def read(path):
    if path == '-':
        return sys.stdin.buffer.read()
    with open(path, 'rb') as f:
        return f.read()


def report(name, unknown, blocked):
    for value in blocked:
        print(f'{name}: blocked: {decode(value)!r}', file=sys.stderr)
    for value in unknown:
        print(f'{name}: not approved: {decode(value)!r}', file=sys.stderr)


def main(argv):
    if len(argv) < 3 or argv[1] not in ('check', 'approve'):
        print(__doc__, file=sys.stderr)
        return 2
    command, paths = argv[1], argv[2:]
    approved = load_approved()
    new, any_blocked = set(), False
    for path in paths:
        unknown, blocked = scan(read(path), approved)
        report(path, unknown, blocked)
        new.update(unknown)
        any_blocked = any_blocked or bool(blocked)
    if command == 'check' or not (new or any_blocked):
        return int(bool(new or any_blocked))
    if any_blocked:
        print('Blocked text can never be approved. Fix the design in Fusion and export again.', file=sys.stderr)
        return 1
    answer = input(f'Approve these {len(new)} for publishing? Type "yes": ')
    if answer.strip() != 'yes':
        return 1
    with open(APPROVED, 'w', encoding='utf-8') as f:
        f.writelines(value + '\n' for value in sorted(approved | new))
    print(f'Added {len(new)} to {os.path.relpath(APPROVED, ROOT)}.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
