"""Tests for pure stored-versus-current resource comparison."""

from setuper.domain.diff import diff_resources
from setuper.domain.models import ResourceSpec


def _resource(
    resource_id: str, type_name: str = "git", value: str = "a"
) -> ResourceSpec:
    """Build one minimal resource spec for comparison."""
    return ResourceSpec(id=resource_id, type=type_name, config={"value": value})


def test_diff_classifies_unchanged_changed_missing_and_added() -> None:
    """Each resource ID is classified by its presence and config equality."""
    stored = [
        _resource("git-repo", value="same"),
        _resource("git-other", value="old"),
        _resource("docker-gone", type_name="docker"),
    ]
    current = [
        _resource("git-repo", value="same"),
        _resource("git-other", value="new"),
        _resource("docker-new", type_name="docker"),
    ]

    result = diff_resources(stored, current)

    statuses = {entry.resource_id: entry.status for entry in result.entries}
    assert statuses == {
        "git-repo": "unchanged",
        "git-other": "changed",
        "docker-gone": "missing",
        "docker-new": "added",
    }


def test_diff_of_identical_lists_is_all_unchanged() -> None:
    """Identical stored and current resources produce no discrepancies."""
    resources = [_resource("git-repo"), _resource("docker-app", type_name="docker")]

    result = diff_resources(resources, resources)

    assert all(entry.status == "unchanged" for entry in result.entries)
    assert len(result.entries) == 2


def test_diff_entries_are_sorted_by_resource_id() -> None:
    """Entries are returned in stable, sorted order regardless of input order."""
    stored = [_resource("zeta"), _resource("alpha")]
    current = [_resource("zeta"), _resource("alpha")]

    result = diff_resources(stored, current)

    assert [entry.resource_id for entry in result.entries] == ["alpha", "zeta"]
