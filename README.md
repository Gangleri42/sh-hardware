# SeedHammer hardware

CAD models of the SeedHammer engraving machine and its Seed controller, exported from Fusion as STEP (AP214, with
colours).

| File | Model | Source |
|---|---|---|
| `hammer/Hammer-v50.step` | SeedHammer engraving machine, complete assembly | Fusion `Hammer_V3P`, version 50 |
| `seed/Seed-v13.step` | Seed controller, V4 without battery | Fusion `seed_v4`, version 13 |

## Notes

- Units: the Seed file is in millimetres, the Hammer file in centimetres. Each file declares its unit, so CAD tools
  import both at the right size.
- The Hammer file holds the machine only; the Seed controller is its own model in `seed/`.
- The Seed includes its circuit board with component models.
- Bought parts (motors, pulleys, connectors, fasteners, the NFC antenna) are modelled for fit. Their designs belong to
  their makers.

## Updating a model

1. Save the design in Fusion.
2. Export the root component as STEP. Fusion leaves hidden components out, so show everything that belongs in the model
   first.
3. Name the file `<Model>-v<version>.step` after the saved version, replace the old file in the same folder, and update
   the table above.

## Viewer

[seedhammer-viewer](https://github.com/Gangleri42/seedhammer-viewer) shows every version of these files in 3D. A
push that changes `seed/` or `hammer/` asks it to rebuild (`.github/workflows/notify-viewer.yml`); each commit that
adds or changes `<Model>-v<version>.step` becomes a version there. Keep the file names in that pattern.

The workflow needs the secret `VIEWER_DISPATCH_TOKEN`: a fine-grained token with resource owner Gangleri42, access to
`seedhammer-viewer` only, and repository permission "Contents: read and write".

## Privacy check

A pre-commit hook rejects local paths, email addresses and Autodesk document ids in staged files, including STEP
headers. Enable it once per clone:

```sh
git config core.hooksPath .githooks
```

## License

Public domain, see [LICENSE](LICENSE). Same as the other SeedHammer repositories.
