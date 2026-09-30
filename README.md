# SeedHammer hardware

CAD models of the Seed controller and the Hammer and II engraving machines, exported from Fusion as STEP (AP214, with
colours).

| File | Model | Source |
|---|---|---|
| `hammer/Hammer-v55.step` | Hammer engraving machine, complete assembly | Fusion `Hammer_V3P`, version 55 |
| `seed/Seed-v15.step` | Seed controller, V4 without battery | Fusion `seed_v4`, version 15 |
| `II/II-v72.step` | II engraving machine, complete assembly | Fusion `SH2_P`, version 72 |

## Notes

- Units: the Seed and II files are in millimetres, the Hammer file in centimetres. Each file declares its unit, so CAD
  tools import all three at the right size.
- The Hammer file holds the machine only; the Seed controller is its own model in `seed/`.
- The Seed includes its circuit board with component models; II includes its mainboard and display.
- Bought parts (motors, pulleys, connectors, fasteners, the NFC antenna) are modelled for fit. Their designs belong to
  their makers.

## Updating a model

1. Save the design in Fusion.
2. Run `ExportToOutbox` (Utilities > Scripts and Add-Ins; add `scripts/fusion/ExportToOutbox` once with "+"). It
   refuses unsaved designs and hidden geometry, and writes `~/SeedHammer/outbox/<Model>-v<version>.step`.
3. Run `scripts/publish.py`. For each file in the outbox it checks that the file is complete and newer than the
   published one, runs the privacy check below, checks that `main` matches `origin/main`, replaces the old file,
   updates the table above, commits, checks the remote again and pushes. Anything that fails moves the file to
   `~/SeedHammer/outbox/held` with a `.reason` file, and nothing is pushed. The header's time stamp is rewritten to UTC, so
   the file doesn't give away the time zone it was exported in; the privacy check refuses any other time stamp.

`scripts/publish.py --dry-run FILE` runs every check without committing.

## Viewer

[seedhammer-viewer](https://github.com/Gangleri42/seedhammer-viewer) shows every version of these files in 3D. A
push that changes `seed/`, `hammer/` or `II/` asks it to rebuild (`.github/workflows/notify-viewer.yml`); each commit
that adds or changes `<Model>-v<version>.step` becomes a version there. Keep the file names in that pattern.

The workflow needs the secret `VIEWER_DISPATCH_TOKEN`: a fine-grained token with resource owner Gangleri42, access to
`seedhammer-viewer` only, and repository permission "Contents: read and write".

## Privacy check

A pre-commit hook rejects local paths, email addresses and Autodesk document ids in staged files. STEP files get a
stricter check (`scripts/step_privacy.py`): every string and comment in the file, header and data alike, must be generated
(colours, numbers, Fusion's import stamps) or listed in `privacy/approved-strings.txt`, after Fusion's instance suffixes
such as ` (1)` and `:3` are removed. A new component name or description holds the file until you approve it:

```sh
scripts/publish.py approve ~/SeedHammer/outbox/held/<Model>-v<version>.step
```

That shows the new strings, adds them to the list on "yes" (the list is committed with the model) and queues the file
again. Paths, addresses, Autodesk ids, URLs and Fusion file names can never be approved.

Enable the hook once per clone:

```sh
git config core.hooksPath .githooks
```

## License

Public domain, see [LICENSE](LICENSE). Same as the other SeedHammer repositories.
