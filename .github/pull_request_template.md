## What this changes

<!-- One or two sentences. Link the issue if there is one. -->

## Why

<!-- The reasoning. This is the part reviewers cannot reconstruct from the diff. -->

## Checklist

- [ ] A test fails before this change and passes after it
- [ ] `make check` passes locally
- [ ] No non-ascii character in any string literal under `src/`
- [ ] No posting path, no platform client, no credential handling added
- [ ] Every model entry still sends `provider.data_collection = "deny"`
- [ ] No em dash or en dash in prose, comments or the commit message
- [ ] Docs updated if behavior or a limit changed
