import pathlib
import re

import pytest
import yaml

_REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
_README_PATH = _REPOSITORY_ROOT / "README.md"
_VERSION_PATH = _REPOSITORY_ROOT / "VERSION"
_ACTION_PATHS = sorted([_REPOSITORY_ROOT / "action.yml", *_REPOSITORY_ROOT.glob("*/action.yml")])
_SELF_REFERENCE_PATTERN = re.compile(r"dandi-cache/dandi-cache-action(?:/[a-z-]+)?@(v[\w.]+)")

#: The exact tag this tree is published under, and the moving major tag a cache actually pins.
_VERSION = _VERSION_PATH.read_text(encoding="utf-8").strip()
_MAJOR_TAG = _VERSION.split(".")[0]


@pytest.mark.ai_generated
def test_version_file_names_an_exact_release() -> None:
    """`VERSION` is compared against the published release tag, so it has to be shaped like one.

    Exact rather than major: the draft release is created from this name, and a draft cannot create
    a tag that already exists. A moving tag can therefore never be the tag a draft names, which is
    why the major tag is moved afterwards instead.
    """
    assert re.fullmatch(r"v\d+\.\d+\.\d+", _VERSION) is not None, _VERSION


@pytest.mark.ai_generated
def test_actions_are_discovered() -> None:
    action_names = [path.parent.name if path.parent != _REPOSITORY_ROOT else "." for path in _ACTION_PATHS]

    assert action_names == [".", "build-and-publish-image"]


@pytest.mark.ai_generated
def test_every_self_reference_names_the_major_tag_being_published() -> None:
    """Nothing in the repository may point at a major tag other than the one `VERSION` implies.

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
        if tag != _MAJOR_TAG
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
