"""Tests for the `Read From Rendered` Write-node button (#427).

The button creates a Read node from the rendered media of a Write node.
When no rendered files exist the user must get a message telling them to
render first instead of an opaque error (issue #427).
"""

import nuke
import pytest

from ayon_nuke.startup import write_to_read


@pytest.fixture(autouse=True)
def dialogs(monkeypatch):
    """Record `nuke.message` dialogs and skip connecting a viewer."""
    recorded = []
    monkeypatch.setattr(nuke, "message", recorded.append)
    monkeypatch.setattr(nuke, "inputs", lambda *args, **kwargs: None)
    return recorded


def _posix(path):
    """Nuke stores and evaluates file paths with forward slashes."""
    return str(path).replace("\\", "/")


def _pattern(directory, name="renderComp"):
    return _posix(directory / f"{name}.####.exr")


def _new_group_with_write(write_pattern):
    """Create a Group with a single Write node using `write_pattern`."""
    nuke.endGroup()
    group = nuke.createNode(
        "Group", "name ReadFromRendered", inpanel=False
    )
    nuke.endGroup()
    with group:
        write_node = nuke.createNode("Write", inpanel=False)
        write_node["file"].setValue(write_pattern)
    return group


def test_missing_render_folder_asks_to_render(dialogs, tmp_path):
    group = _new_group_with_write(_pattern(tmp_path / "not_rendered_yet"))

    write_to_read.write_to_read(group)

    assert len(dialogs) == 1
    assert "no rendered files" in dialogs[0]
    assert "not_rendered_yet" in dialogs[0]
    assert "Render the Write node first" in dialogs[0]
    assert nuke.allNodes("Read") == []


def test_empty_render_folder_asks_to_render(dialogs, tmp_path):
    directory = tmp_path / "renders"
    directory.mkdir()
    group = _new_group_with_write(_pattern(directory))

    write_to_read.write_to_read(group)

    assert len(dialogs) == 1
    assert "no rendered files" in dialogs[0]
    assert nuke.allNodes("Read") == []


def test_missing_single_file_asks_to_render(dialogs, tmp_path):
    group = _new_group_with_write(_posix(tmp_path / "missing.mov"))

    write_to_read.write_to_read(group)

    assert len(dialogs) == 1
    assert "no rendered files" in dialogs[0]
    assert nuke.allNodes("Read") == []


def test_rendered_sequence_is_detected(tmp_path):
    directory = tmp_path / "renders"
    directory.mkdir()
    for frame in (1000, 1001, 1002, 1003):
        (directory / f"renderComp.{frame:04d}.exr").write_text("")

    filepath, first_frame, last_frame = write_to_read.detect_file_on_disk(
        _pattern(directory),
        _posix(directory / "renderComp.1000.exr"),
        "",
        1001,
        False,
    )

    assert filepath.endswith("renderComp.####.exr")
    assert (first_frame, last_frame) == (1000, 1003)


def test_single_file_is_read(dialogs, tmp_path):
    movie = tmp_path / "movie.mov"
    movie.write_text("")
    group = _new_group_with_write(_posix(movie))

    write_to_read.write_to_read(group)

    assert dialogs == []
    read_nodes = nuke.allNodes("Read")
    assert len(read_nodes) == 1
    assert read_nodes[0]["file"].value() == _posix(movie)


def test_project_directory_none_does_not_raise(tmp_path):
    """Issue #427: a `None` project directory used to reach clique."""
    directory = tmp_path / "renders"
    directory.mkdir()
    for frame in (1000, 1001):
        (directory / f"renderComp.{frame:04d}.exr").write_text("")

    filepath, _first_frame, _last_frame = (
        write_to_read.detect_file_on_disk(
            _pattern(directory),
            _posix(directory / "renderComp.1000.exr"),
            None,
            1001,
            False,
        )
    )

    assert filepath is not None
