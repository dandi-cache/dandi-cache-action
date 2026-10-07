import pathlib
import re

import pytest
import yaml

_REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
_README_PATH = _REPOSITORY_ROOT / "README.md"
_VERSION_PATH = _REPOSITORY_ROOT / "VERSION"
_ACTION_PATHS = sorted([_REPOSITORY_ROOT / "action.yml", *_REPOSITORY_ROOT.glob("*/action.yml")])
_SELF_REFERENCE_PATTERN = re.compile(r"dandi-cache/dandi-cache-action(?:/[a-z-]+)?@(v[\w.]+)")

#: The tag this tree is published under, which is the tag a cache pins.
_VERSION = _VERSION_PATH.read_text(encoding="utf-8").strip()


@pytest.mark.ai_generated
def test_version_file_names_a_single_integer_tag() -> None:
    """These actions are versioned by one integer, so anything finer than that is not a tag here.

    A cache pins this tag and the tag moves, so the version a cache depends on is the interface,
    not the tree. A `vX.Y.Z` would offer a precision this repository does not keep.
    """
    assert re.fullmatch(r"v\d+", _VERSION) is not None, _VERSION


@pytest.mark.ai_generated
def test_actions_are_discovered() -> None:
    action_names = [path.parent.name if path.parent != _REPOSITORY_ROOT else "." for path in _ACTION_PATHS]

    assert action_names == [".", "build-and-publish-image"]


@pytest.mark.ai_generated
def test_every_self_reference_names_the_version_being_published() -> None:
    """Nothing in the repository may point at a tag other than the one `VERSION` names.

    A reference left on the previous tag resolves and runs, and keeps running what it ran the day it
    was written, so neither a test of the files against each other nor a workflow run catches it.
    The expected tag comes from `VERSION` rather than from a literal here, because a literal only
    proves the references agree with this test, which every one of them naming the old tag satisfies
    just as well.
    """
    sources = [_README_PATH, *_ACTION_PATHS]

    stale = {
        f"{path.relative_to(_REPOSITORY_ROOT)}: {tag}"
        for path in sources
        for tag in _SELF_REFERENCE_PATTERN.findall(path.read_text(encoding="utf-8"))
        if tag != _VERSION
    }

    assert stale == set()


@pytest.mark.ai_generated
@pytest.mark.parametrize("action_path", _ACTION_PATHS, ids=lambda path: path.parent.name or "root")
def test_every_run_step_declares_its_shell(action_path: pathlib.Path) -> None:
    """A composite action has no default shell, so a `run` without one fails when it is reached."""
    action = yaml.safe_load(action_path.read_text(encoding="utf-8"))

    assert action["runs"]["using"] == "composite"
    for step in action["runs"]["steps"]:
        if "run" in step:
            assert step.get("shell") == "bash", step.get("name")


@pytest.mark.ai_generated
@pytest.mark.parametrize("action_path", _ACTION_PATHS, ids=lambda path: path.parent.name or "root")
def test_every_optional_input_has_a_default(action_path: pathlib.Path) -> None:
    action = yaml.safe_load(action_path.read_text(encoding="utf-8"))

    for name, specification in action.get("inputs", {}).items():
        assert specification.get("required") is True or "default" in specification, name


@pytest.mark.ai_generated
def test_the_image_is_pushed_only_after_every_check() -> None:
    """A tag on ghcr must only ever name an image that passed the checks.

    When the build step pushed, `:latest` was published before any check ran, so a failing check
    reported on an image every cache was already pulling. The build now only loads the image, and
    the one step that pushes comes after every step that runs something against it.
    """
    action = yaml.safe_load((_REPOSITORY_ROOT / "build-and-publish-image" / "action.yml").read_text(encoding="utf-8"))
    steps = action["runs"]["steps"]

    build = next(step for step in steps if step.get("uses", "").startswith("docker/build-push-action@"))
    assert build["with"]["push"] is False
    assert build["with"]["load"] is True

    pushes = [index for index, step in enumerate(steps) if "docker push" in step.get("run", "")]
    checks = [index for index, step in enumerate(steps) if "docker run" in step.get("run", "")]
    assert len(pushes) == 1
    assert checks
    assert pushes[0] > max(checks)


def _update_step(name: str) -> str:
    action = yaml.safe_load((_REPOSITORY_ROOT / "action.yml").read_text(encoding="utf-8"))
    return next(step for step in action["runs"]["steps"] if step.get("name") == name)


_CHAIN_STEP_NAME = "Queue the next run while a backlog remains"
_GATE_STEP_NAME = "Skip if a run started since this one was triggered has already succeeded"

#: A stand-in for `gh`: canned JSON per subcommand, filtered through `jq` the way `gh --jq` does, and
#: a record of every `workflow run` it was asked to make.
_STUB_GH = """#!/bin/bash
jq_expression=""; previous=""
for argument in "$@"; do [ "$previous" = "--jq" ] && jq_expression="$argument"; previous="$argument"; done
case "$*" in
  "run view"*) echo "{\\"createdAt\\":\\"$STUB_CREATED\\"}" | jq -r "$jq_expression";;
  "run list"*"--status success"*) echo "$STUB_SUCCESSES" | jq -r "$jq_expression";;
  "run list"*) echo "$STUB_RUNS" | jq -r "$jq_expression";;
  "workflow run"*) echo "$*" >> "$STUB_CALLS"; exit "${STUB_DISPATCH_EXIT:-0}";;
esac
"""


def _run_step(step_name: str, tmp_path: pathlib.Path, environment: dict) -> tuple[str, str]:
    """Run one step's script the way a composite action does, against the stub `gh`."""
    import os
    import shutil
    import subprocess

    if shutil.which("jq") is None or shutil.which("bash") is None:
        pytest.skip("needs bash and jq")
    script = (
        _update_step(step_name)["run"]
        .replace("${{ github.repository }}", "dandi-cache/example")
        .replace("${{ github.run_id }}", "1")
        .replace("${{ github.workflow }}", "Update")
        .replace("${{ github.ref_name }}", "main")
    )
    stub_directory = tmp_path / "bin"
    stub_directory.mkdir(exist_ok=True)
    (stub_directory / "gh").write_text(_STUB_GH)
    (stub_directory / "gh").chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    output = tmp_path / "output"
    completed = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", script],
        env={
            **os.environ,
            "PATH": f"{stub_directory}:{os.environ['PATH']}",
            "STUB_CALLS": str(calls),
            "GITHUB_OUTPUT": str(output),
            **environment,
        },
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return calls.read_text(), output.read_text() if output.exists() else ""


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("batch", "new", "runs", "dispatch_exit", "expect_dispatch"),
    [
        pytest.param(500, 120, '[{"status": "in_progress"}]', 0, True, id="backlog-left"),
        pytest.param(380, 380, '[{"status": "in_progress"}]', 0, False, id="batch-not-full"),
        pytest.param(500, 0, '[{"status": "in_progress"}]', 0, False, id="nothing-new"),
        pytest.param(500, 120, '[{"status": "in_progress"}, {"status": "pending"}]', 0, False, id="another-waiting"),
        pytest.param(None, None, "[]", 0, False, id="no-batch-log"),
        pytest.param(500, 120, '[{"status": "in_progress"}]', 1, True, id="dispatch-refused-is-not-a-failure"),
    ],
)
def test_an_update_queues_the_next_run_only_while_a_backlog_remains(
    tmp_path: pathlib.Path, batch, new, runs, dispatch_exit, expect_dispatch
) -> None:
    """Chain on a full batch that made progress, and on nothing else.

    A full batch that recorded nothing would chain the same failures forever, and a run queued
    while another waits would cancel it where workflows share a concurrency group.
    """
    logs = tmp_path / "derivatives-dataset" / "logs"
    logs.mkdir(parents=True)
    if batch is not None:
        (logs / "update_2026-10-04T10-00-00Z.log").write_text(
            f"INFO Processing {batch} items (100 already recorded).\n"
            f"INFO Wrote 600 records to /tmp/derivatives/x.jsonl ({new} new, 3 failed) in 1.0 min\n"
        )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "cache.toml").write_text("[operations.update]\nlimit = 500\n")

    calls, _ = _run_step(
        _CHAIN_STEP_NAME,
        tmp_path,
        {
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_WORKSPACE": str(workspace),
            "OPERATION": "update",
            "LIMIT": "",
            "WORKFLOW_REF": "dandi-cache/example/.github/workflows/update.yml@refs/heads/main",
            "STUB_RUNS": runs,
            "STUB_DISPATCH_EXIT": str(dispatch_exit),
        },
    )
    assert bool(calls) is expect_dispatch
    if expect_dispatch:
        assert calls.startswith("workflow run update.yml --repo dandi-cache/example --ref main")


@pytest.mark.ai_generated
def test_only_an_update_outside_testing_chains() -> None:
    """A refresh's batch is always full, so it would never stop; a testing run writes nothing real."""
    condition = _update_step(_CHAIN_STEP_NAME)["if"]
    assert "inputs.operation == 'update'" in condition
    assert "inputs.testing != 'true'" in condition
    assert "steps.gate.outputs.should-run == 'true'" in condition


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("successes", "should_run"),
    [
        pytest.param('[{"startedAt": "2026-10-04T10:00:00Z"}]', "true", id="queued-behind-an-earlier-run"),
        pytest.param(
            '[{"startedAt": "2026-10-04T12:30:00Z"}, {"startedAt": "2026-10-04T10:00:00Z"}]',
            "false",
            id="a-later-run-already-succeeded",
        ),
        pytest.param("[]", "true", id="no-successes"),
    ],
)
def test_a_queued_run_is_skipped_only_when_a_later_started_run_succeeded(
    tmp_path: pathlib.Path, successes: str, should_run: str
) -> None:
    """A run that was already going when this one was queued did not cover it.

    That is the run a chained or scheduled run waits behind, and with a batch limit it left the
    rest of the backlog. The gate used to skip on any run *finishing* after this one was queued,
    which skipped exactly the run that should follow it.
    """
    _, output = _run_step(
        _GATE_STEP_NAME,
        tmp_path,
        {"STUB_CREATED": "2026-10-04T12:00:00Z", "STUB_SUCCESSES": successes},
    )
    assert output.strip() == f"should-run={should_run}"


_RELEASE_WORKFLOW_PATH = _REPOSITORY_ROOT / ".github" / "workflows" / "prepare_release.yml"


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("released", "changed_path", "expect_exit", "expect_prepare"),
    [
        pytest.param(True, ".pre-commit-config.yaml", 0, "false", id="released-and-no-action-changed"),
        pytest.param(True, "action.yml", 1, None, id="released-and-the-action-changed"),
        pytest.param(True, "build-and-publish-image/action.yml", 1, None, id="released-and-a-nested-action-changed"),
        pytest.param(False, "action.yml", 0, "true", id="not-released-yet"),
    ],
)
def test_a_frozen_version_refuses_only_a_change_to_an_action(
    tmp_path: pathlib.Path, released: bool, changed_path: str, expect_exit: int, expect_prepare: str | None
) -> None:
    """A pre-commit autoupdate on a released version is not a forgotten bump.

    Failing on it sent a failure notice every quarter for a merge that changed nothing a cache runs.
    """
    import os
    import shutil
    import subprocess

    if shutil.which("git") is None or shutil.which("bash") is None:
        pytest.skip("needs bash and git")
    workflow = yaml.safe_load(_RELEASE_WORKFLOW_PATH.read_text(encoding="utf-8"))
    (step,) = [step for step in workflow["jobs"]["Draft"]["steps"] if step.get("id") == "frozen"]

    def git(*arguments: str, cwd: pathlib.Path) -> str:
        return subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True).stdout

    origin = tmp_path / "origin.git"
    git("init", "--quiet", "--bare", str(origin), cwd=tmp_path)
    clone = tmp_path / "clone"
    git("init", "--quiet", str(clone), cwd=tmp_path)
    git("config", "user.email", "test@example.com", cwd=clone)
    git("config", "user.name", "test", cwd=clone)
    git("remote", "add", "origin", str(origin), cwd=clone)
    for path in ("action.yml", "build-and-publish-image/action.yml", ".pre-commit-config.yaml"):
        (clone / path).parent.mkdir(parents=True, exist_ok=True)
        (clone / path).write_text("before\n")
    git("add", ".", cwd=clone)
    git("commit", "--quiet", "-m", "released", cwd=clone)
    if released:
        git("tag", "v5", cwd=clone)
    (clone / changed_path).write_text("after\n")
    git("commit", "--quiet", "-am", "merged", cwd=clone)

    stub_directory = tmp_path / "bin"
    stub_directory.mkdir()
    (stub_directory / "gh").write_text(f"#!/bin/bash\necho {'false' if released else ''}\n")
    (stub_directory / "gh").chmod(0o755)
    output = tmp_path / "output"
    completed = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", step["run"]],
        cwd=clone,
        env={
            **os.environ,
            "PATH": f"{stub_directory}:{os.environ['PATH']}",
            "TAG": "v5",
            "GITHUB_SHA": git("rev-parse", "HEAD", cwd=clone).strip(),
            "GITHUB_OUTPUT": str(output),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        },
        capture_output=True,
        text=True,
    )
    assert completed.returncode == expect_exit, completed.stderr
    if expect_prepare is not None:
        assert output.read_text().strip() == f"prepare={expect_prepare}"


@pytest.mark.ai_generated
def test_dist_is_staged_by_the_pipeline_and_published_as_files() -> None:
    """The pipeline stages `dist` and dist-bundle-action publishes it, so every consumer URL stays the same."""
    action = yaml.safe_load((_REPOSITORY_ROOT / "action.yml").read_text(encoding="utf-8"))
    names = [step.get("name") for step in action["runs"]["steps"]]
    run = _update_step("Run the update with provenance")
    publish = _update_step("Publish dist")

    assert run["env"]["PUBLISH_DIST"] == "false"
    assert re.fullmatch(r"CodyCBakerPhD/dist-bundle-action@v\d+", publish["uses"]) is not None
    assert publish["with"]["format"] == "files"
    assert publish["with"]["root"] == "${{ steps.run.outputs.dist-directory }}"
    assert "steps.run.outputs.dist-directory != ''" in publish["if"]
    assert names.index("Publish dist") == names.index("Run the update with provenance") + 1


def test_files_nearing_the_size_limit_send_their_own_notification() -> None:
    """The pipeline reports files near GitHub's limit as step outputs, and those reach someone even on a green run."""
    notify = _update_step("Notify on files nearing GitHub's size limit")

    assert notify["uses"].startswith("dawidd6/action-send-mail@")
    assert notify["if"].startswith("${{ always() && inputs.mail-username != ''")
    for output in ("steps.run.outputs.size-warnings", "steps.run.outputs.dist-size-warnings"):
        assert f"{output} != ''" in notify["if"]
        assert output in notify["with"]["body"]
