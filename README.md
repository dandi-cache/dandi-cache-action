# dandi-cache-action

The GitHub Actions every [DANDI Cache](https://github.com/dandi-cache) repository runs.

A cache is one operation around a shared pipeline. The pipeline itself lives in
[`dandi-cache-utils`](https://github.com/dandi-cache/dandi-cache-utils) and ships inside the
cache's runtime image; these actions are the thin CI layer that drives it, versioned by their own
interface so a cache can pin them independently of the library.

## `dandi-cache/dandi-cache-action` — run a cache update

Skips a run that was overtaken while queued, builds the runner's environment, pulls the cache's
runtime image, extracts the shared pipeline from it, and runs the update with full DataLad
provenance.

```yaml
name: Update

on:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:
    inputs:
      testing:
        type: boolean
        default: false
      limit:
        type: string
        default: ""

# An in-progress update is never cancelled; a run triggered while one is executing waits, and the
# action then skips it once it starts, because the update it would perform has just been done.
concurrency:
  group: ${{ github.workflow }}
  cancel-in-progress: false

jobs:
  Update:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: read
    # So a hung network read cannot burn a full six hours.
    timeout-minutes: 330
    steps:
      - uses: dandi-cache/dandi-cache-action@v0
        with:
          token: ${{ secrets._GITHUB_API_KEY }}
          testing: ${{ inputs.testing || false }}
          limit: ${{ inputs.limit || '' }}
          mail-username: ${{ secrets.MAIL_USERNAME }}
          mail-password: ${{ secrets.MAIL_PASSWORD }}
```

| Input | Default | Meaning |
|---|---|---|
| `token` | *required* | Checks out the repository, pushes the results, reads the runtime image. Needs `contents: write` on the cache and `read:packages`. |
| `operation` | `update` | Which entry point from the cache's `[operations]` table to run. |
| `testing` | `false` | Process a handful of items into `testing_`-prefixed files, leaving the cache untouched. |
| `limit` | *the cache's* | Cap on new items processed this run. |
| `image` | *the cache's* | Runtime image; empty uses the one `cache.toml` declares. |
| `mail-username` / `mail-password` | empty | SMTP credentials for the failure notification. Empty sends no mail. |
| `notify-to` | `cody.c.baker.phd@gmail.com` | Who to notify. |

It outputs `ran`: `true` when the update ran, `false` when it was skipped as already done.

A cache with a second entry point adds a second job passing `operation:`.

## `dandi-cache/dandi-cache-action/build-and-publish-image` — build and publish the runtime image

```yaml
jobs:
  BuildAndPush:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: dandi-cache/dandi-cache-action/build-and-publish-image@v0
        with:
          token: ${{ secrets._GITHUB_API_KEY }}
          mail-username: ${{ secrets.MAIL_USERNAME }}
          mail-password: ${{ secrets.MAIL_PASSWORD }}
```

`main` publishes `:latest` and the commit SHA; another branch publishes `dev-<branch>` and the SHA,
so an environment change can be tested without overwriting `:latest`; a pull request only builds.
The build then checks that the image really was built `FROM` the shared base, because the update
extracts the orchestration from it at run time — catching a Dockerfile that is not, here rather
than in the cache's next scheduled update.

| Input | Default | Meaning |
|---|---|---|
| `token` | *required* | Pushes the image. Needs `write:packages`. |
| `dockerfile` | `containers/Dockerfile` | What to build. |
| `target` | empty | Build stage, for a multi-stage Dockerfile. |
| `mail-username` / `mail-password` / `notify-to` | as above | The failure notification. |

## Why a repository of its own

These are *referenced*, not copied: a cache says `uses:` and gets whatever this repository publishes
at the tag it pins, so a fix reaches every cache at once without touching any of them. Keeping them
apart from the library means they are versioned by their own interface — the inputs above — rather
than by the library's release cadence, and a cache can pin `@v0` while tracking the image
separately.

The [cache template](https://github.com/dandi-cache/cache-template) is the other side of that line:
what it holds is copied once when a cache is generated, and owned by the cache from then on.
