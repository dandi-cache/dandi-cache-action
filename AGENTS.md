# Agent instructions

The organization's conventions, as set out in
[`CodyCBakerPhD/historia`](https://github.com/CodyCBakerPhD/historia/blob/main/AGENTS.md) and
[`dandi-cache-utils`](https://github.com/dandi-cache/dandi-cache-utils/blob/main/AGENTS.md), for a
repository that holds actions rather than a package.

## What belongs here

Composite actions, and nothing else. The orchestration these actions run is the
`dandi_cache_utils.pipeline` script, which ships inside the cache's runtime image; an action pulls
that image, extracts the package and runs the script. Logic that belongs to the pipeline goes in
[`dandi-cache-utils`](https://github.com/dandi-cache/dandi-cache-utils), not into a `run:` step
here.

Name an action for what it does, in full. `build-and-publish-image`, not `image`. The directory
name is the reference a cache writes, so it is user-facing.

## Versioning

- These actions are versioned by their own interface, the inputs, rather than by the library's
  release cadence. A cache pins a tag here and tracks the runtime image separately.
- A change that alters or removes an input is breaking and needs a new major tag. Adding an
  optional input with a default is not.
- The moving major tag (`v0`) follows the latest release on that major.

## Commits and PRs

- Always run `pre-commit` before committing and pushing changes.
- Always link PRs to issues when possible.
- PR titles should be human-readable and in the past tense. They should NOT use conventional commit
  style.
- Every commit must include a `Co-Authored-By` trailer identifying the tool and the model that
  wrote it.

## Writing an action

- Every `run` step declares `shell: bash`. A composite action has no default shell.
- A composite action cannot read `secrets.*`. Take what is needed as a named input, and never
  accept a blanket credential where a specific one will do.
- A composite action cannot set `runs-on`, `permissions` or `timeout-minutes` for its caller.
  Document what the calling job has to set, in the README, next to the example.
- Keep inputs to what a cache genuinely varies. An input that exists for one caller belongs in that
  caller.
- Avoid excessive em-dashes, colons, and semicolons in written text such as documentation. Prefer
  breaking into separate, shorter sentences instead.
- Keep inline comments sparse. Explain non-obvious "why", never "what".

## Verifying a change

An action cannot be exercised except by a workflow that calls it, so a change here is verified by
a cache repository running it. Before merging, check that the YAML parses, that every `run` step
declares its shell, and that every input the bodies reference is declared. After merging, watch the
first cache run that picks it up.
