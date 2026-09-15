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
