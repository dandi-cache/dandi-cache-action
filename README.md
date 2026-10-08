# dandi-cache-action

The common GitHub Actions used by every [DANDI Cache](https://github.com/dandi-cache) repository.

A cache is one operation around a shared pipeline.
The pipeline itself lives in [`dandi-cache-utils`](https://github.com/dandi-cache/dandi-cache-utils) and ships inside the cache's runtime image; these actions are the thin CI layer that drives it, versioned by their own interface so a cache can pin them independently of the library.

## `dandi-cache/dandi-cache-action` — run a cache update

Skips a run that was overtaken while queued, builds the runner's environment, pulls the cache's runtime image, extracts the shared pipeline from it, and runs the update with full DataLad provenance.

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
      - uses: dandi-cache/dandi-cache-action@v7
        with:
          token: ${{ secrets._GITHUB_API_KEY }}
          testing: ${{ inputs.testing || false }}
          limit: ${{ inputs.limit || '' }}
          mail-username: ${{ secrets.MAIL_USERNAME }}
          mail-password: ${{ secrets.MAIL_PASSWORD }}
```

| Input | Default | Meaning |
|---|---|---|
| `token` | *required* | Checks out the repository, pushes the results, reads the runtime image, and queues the next run. Needs `contents: write` and `actions: write` on the cache, and `read:packages`. |
| `operation` | `update` | Which entry point from the cache's `[operations]` table to run. |
| `testing` | `false` | Process a handful of items into `testing_`-prefixed files, leaving the cache untouched. |
| `limit` | *the cache's* | Cap on new items processed this run. |
| `image` | *the cache's* | Runtime image; empty uses the one `cache.toml` declares. |
| `chain` | `true` | Queue the next run when an update ends with backlog left. `false` leaves it to the schedule. |
| `mail-username` / `mail-password` | empty | SMTP credentials for the notifications: a failed run, and a file past 80% of GitHub's 100 MiB limit on `derivatives` or `dist` (sent even when the run succeeds). Empty sends no mail. |
| `notify-to` | `cody.c.baker.phd@gmail.com` | Who to notify. |

It outputs `ran`: `true` when the update ran, `false` when it was skipped as already done.

A cache with a second entry point adds a second job passing `operation:`.

### Runs follow each other while a backlog remains

GitHub delays and drops scheduled runs under load, so a cache with a backlog used to sit idle for hours between runs whatever its cron asked for.
An update that ends with backlog left now queues the next run itself, as soon as it finishes.
Backlog is left when its batch was full and it recorded something new; the second condition keeps a run that only re-fails the same items from chaining forever.
Both are read from the run's own log, the library's `Processing N items` and `(K new, …)` lines.

Only `update` chains, since a refresh re-assesses what is already recorded and its batch is always full.
Nothing is queued while another run of the repository is waiting, which matters where workflows share a concurrency group: a new pending run would cancel the waiting one.
A dispatch the token is not allowed to make is a warning, not a failed update, and the schedule starts the next run instead.

A queued run is skipped only when a run that *started* after it was queued has since succeeded, since that run read everything it would have.
Until `@v5` it was skipped when any run *finished* after it was queued, which skipped exactly the run that should follow a long one: the run it waited behind had left the rest of the backlog.

### `dist` is published by `dist-bundle-action`

The pipeline stages the `dist` content, each declared output compressed beside `dataset_description.json`, and [`CodyCBakerPhD/dist-bundle-action`](https://github.com/CodyCBakerPhD/dist-bundle-action) publishes it with its `files` format.
That writes the same files to the same paths as the pipeline's own push did, so every consumer URL is unchanged.
The branch still holds a single commit, and a run that changed nothing in it leaves it alone rather than force-pushing an identical commit.
Until `@v6` the pipeline pushed `dist` itself.

## `dandi-cache/dandi-cache-action/build-and-publish-image` — build and publish the runtime image

```yaml
jobs:
  BuildAndPush:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: dandi-cache/dandi-cache-action/build-and-publish-image@v7
        with:
          token: ${{ secrets._GITHUB_API_KEY }}
          mail-username: ${{ secrets.MAIL_USERNAME }}
          mail-password: ${{ secrets.MAIL_PASSWORD }}
```

`main` publishes `:latest` and the commit SHA; another branch publishes `dev-<branch>` and the SHA, so an environment change can be tested without overwriting `:latest`; a pull request only builds.
The build then checks that the image really was built `FROM` the shared base, because the update extracts the orchestration from it at run time — catching a Dockerfile that is not, here rather than in the cache's next scheduled update.

It then checks the cache's committed `dataset_description.json` against the `cache.toml` it is rendered from, so the copy a repository carries cannot drift from the one it publishes.
That file is generated — `dandi-cache dataset-description --declared --output dataset_description.json` — and a cache that commits none passes, since adopting the file is what makes it checked.

Finally it checks the cache's own operation scripts, through `dandi-cache check-operations`, against the library the image carries.
Those two checks prove the image and the configuration and never touch `code/update.py`, which is the one file a cache actually contributes, so a script naming a function the image's library does not have used to pass everything and fail at the next scheduled update.
The check reads the syntax tree rather than importing the script, because a name used inside a function body is resolved when that function runs, and it covers every operation a cache declares rather than only `update`.
It needs a base image carrying `dandi-cache-utils` 0.1.8 or newer, which is part of what adopting `@v3` means.

The image is pushed only once every one of these checks has passed.
Until `@v4` it was pushed first and checked afterwards, so a failing check reported on an image that was already `:latest` and already what the next scheduled update would pull.
Now a tag on ghcr only ever names an image that passed, and a failed build leaves the previous `:latest` in place.

| Input | Default | Meaning |
|---|---|---|
| `token` | *required* | Pushes the image. Needs `write:packages`. |
| `dockerfile` | `containers/Dockerfile` | What to build. |
| `target` | empty | Build stage, for a multi-stage Dockerfile. |
| `mail-username` / `mail-password` / `notify-to` | as above | The failure notification. |

## Why a repository of its own

These are *referenced*, not copied: a cache says `uses:` and gets exactly the tree the tag it pins was frozen at, so what a cache runs is decided by one line in its own workflow rather than by whatever landed here since.
A release freezes its tag, so adopting a newer one is a deliberate edit in the cache; the trade is that nothing here can change under a cache that has not asked for it.
Keeping them apart from the library means they are versioned by their own interface — the inputs above — rather than by the library's release cadence, and a cache can pin `@v7` while tracking the image separately.

The [cache template](https://github.com/dandi-cache/cache-template) is the other side of that line: what it holds is copied once when a cache is generated, and owned by the cache from then on.
