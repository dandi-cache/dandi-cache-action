# Agent instructions

The organization's conventions, as set out in [`CodyCBakerPhD/historia`](https://github.com/CodyCBakerPhD/historia/blob/main/AGENTS.md) and [`dandi-cache-utils`](https://github.com/dandi-cache/dandi-cache-utils/blob/main/AGENTS.md), for a repository that holds actions rather than a package.

## What belongs here

Composite actions, and nothing else.
The orchestration these actions run is the `dandi_cache_utils.pipeline` script, which ships inside the cache's runtime image; an action pulls that image, extracts the package and runs the script.
Logic that belongs to the pipeline goes in [`dandi-cache-utils`](https://github.com/dandi-cache/dandi-cache-utils), not into a `run:` step here.

Name an action for what it does, in full.
`build-and-publish-image`, not `image`.
The directory name is the reference a cache writes, so it is user-facing.

## Versioning

- These actions are versioned by their own interface, the inputs, rather than by the library's release cadence.
  A cache pins a tag here and tracks the runtime image separately.
- A tag here is a single integer, `v2`.
  Never `vX.Y.Z`.
  A cache pins the integer, so what it depends on is the interface rather than the tree, and a
  finer tag would offer a precision this repository does not keep.
  The tests reject anything else.
- **A release freezes its tag.**
  A version may move while it is unreleased, which is what the draft's target does on every merge,
  and stops moving the moment it is published.
  A released tag is never re-pointed, so a cache pinned to one keeps running exactly the tree it
  was pinned to.
- The next release is therefore the next integer, not a re-cut of the last one.
  That is true of a fix as much as of a breaking change, since neither can reach a frozen tag.
- Adopting a release is an edit in the cache, one line in its workflow.
  Nothing here reaches a cache that has not asked for it, which is the point of freezing rather
  than a cost of it.
- `VERSION` holds the tag being prepared, and is the only place it is decided.
  Bump it in the same commit that rewrites the references to this repository, since the tests read
  it rather than a literal and a reference left on the previous integer fails before the commit
  lands.
- Release by publishing the draft that `Prepare release draft` keeps on every merge to `main`.
  Its tag name comes from `VERSION` and its target from that commit, so the tag is never typed,
  and publishing is what creates it.
  The workflow refuses to prepare a version that has already been released, and refuses a tag
  standing with no release behind it, since publishing would attach to that tag rather than to the
  tree the draft names.
- The `action-versions-agree` pre-commit hook runs the test that catches a reference drifting from
  the tag `VERSION` names.
  Those references are written by hand, so it fails at commit time rather than leaving it to CI.

## Commits and PRs

- Always run `pre-commit` before committing and pushing changes.
- Always link PRs to issues when possible.
- PR titles should be human-readable and in the past tense.
  They should NOT use conventional commit style.
- Every commit must include a `Co-Authored-By` trailer identifying the tool and the model that wrote it.

## Writing an action

- Every `run` step declares `shell: bash`.
  A composite action has no default shell.
- A composite action cannot read `secrets.*`.
  Take what is needed as a named input, and never accept a blanket credential where a specific one will do.
- A composite action cannot set `runs-on`, `permissions` or `timeout-minutes` for its caller.
  Document what the calling job has to set, in the README, next to the example.
- Keep inputs to what a cache genuinely varies.
  An input that exists for one caller belongs in that caller.
- Avoid excessive em-dashes, colons, and semicolons in written text such as documentation.
  Prefer breaking into separate, shorter sentences instead.
- In Markdown, give each sentence its own line rather than wrapping prose to a fixed width.
  A reworded sentence is then a one-line diff instead of a reflowed paragraph, which is what makes a prose suggestion on a pull request reviewable.
- Keep inline comments sparse.
  Explain non-obvious "why", never "what".

## Verifying a change

An action cannot be exercised except by a workflow that calls it, so a change here is verified by a cache repository running it.
Before merging, check that the YAML parses, that every `run` step declares its shell, and that every input the bodies reference is declared.
After merging, watch the first cache run that picks it up.
