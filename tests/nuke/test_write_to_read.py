"""Tests for the `Read From Rendered` Write-node button (#427).

The button creates a Read node from the rendered media of a Write node.
When nothing has been rendered yet the Read node is prepared for the
future render path instead of failing (issue #427, PR #428).
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


@pytest.fixture
def frame_range():
    """Set a workfile frame range and return it."""
    first_frame, last_frame = 1001, 1050
    root = nuke.root()
    root["first_frame"].setValue(first_frame)
    root["last_frame"].setValue(last_frame)
    return first_frame, last_frame


def _posix(path):
    """Nuke stores and evaluates file paths with forward slashes."""
    return str(path).replace("\\", "/")


def _pattern(directory, name="renderComp"):
    return _posix(directory / f"{name}.####.exr")


def _render(directory, frames, name="renderComp"):
    """Create fake rendered frames in `directory`."""
    directory.mkdir(parents=True, exist_ok=True)
    for frame in frames:
        (directory / f"{name}.{frame:04d}.exr").write_text("")


def _new_group_with_write(
    write_pattern, use_limit=False, first_frame=None, last_frame=None
):
    """Create a Group with a single Write node using `write_pattern`."""
    nuke.endGroup()
    group = nuke.createNode(
        "Group", "name ReadFromRendered", inpanel=False
    )
    nuke.endGroup()
    with group:
        write_node = nuke.createNode("Write", inpanel=False)
        write_node["file"].setValue(write_pattern)
        if use_limit:
            write_node["use_limit"].setValue(True)
            if first_frame is not None:
                write_node["first"].setValue(first_frame)
            if last_frame is not None:
                write_node["last"].setValue(last_frame)
    return group


def _new_group_with_deep_write(write_pattern):
    """Create a Group with a single DeepWrite node using `write_pattern`."""
    nuke.endGroup()
    group = nuke.createNode(
        "Group", "name ReadFromDeepWrite", inpanel=False
    )
    nuke.endGroup()
    with group:
        write_node = nuke.createNode("DeepWrite", inpanel=False)
        write_node["file"].setValue(write_pattern)
    return group


# -- Preparing a Read before anything is rendered --------------------------


def test_missing_render_folder_prepares_read(
    dialogs, frame_range, tmp_path
):
    first_frame, last_frame = frame_range
    pattern = _pattern(tmp_path / "not_rendered_yet")
    group = _new_group_with_write(pattern)

    write_to_read.write_to_read(group)

    assert len(dialogs) == 1
    assert "is prepared" in dialogs[0]
    assert "not_rendered_yet" in dialogs[0]

    read_nodes = nuke.allNodes("Read")
    assert len(read_nodes) == 1
    read = read_nodes[0]
    assert "not_rendered_yet" in read["file"].value()
    assert read["label"].value() == write_to_read.PREPARED_LABEL
    assert read["first"].value() == first_frame
    assert read["last"].value() == last_frame


def test_prepared_read_uses_write_frame_range(
    dialogs, frame_range, tmp_path
):
    pattern = _pattern(tmp_path / "not_rendered_yet")
    group = _new_group_with_write(
        pattern, use_limit=True, first_frame=1005, last_frame=1010
    )

    write_to_read.write_to_read(group)

    read = nuke.allNodes("Read")[0]
    assert read["first"].value() == 1005
    assert read["last"].value() == 1010


def test_prepared_read_is_not_duplicated(dialogs, frame_range, tmp_path):
    pattern = _pattern(tmp_path / "not_rendered_yet")
    group = _new_group_with_write(pattern)

    write_to_read.write_to_read(group)
    write_to_read.write_to_read(group)

    assert len(nuke.allNodes("Read")) == 1


def test_prepared_read_is_promoted_when_rendered(
    dialogs, frame_range, tmp_path
):
    directory = tmp_path / "renders"
    pattern = _pattern(directory)
    group = _new_group_with_write(pattern)

    write_to_read.write_to_read(group)
    assert len(dialogs) == 1
    prepared = nuke.allNodes("Read")[0]
    assert prepared["label"].value() == write_to_read.PREPARED_LABEL

    _render(directory, range(1001, 1011))
    nuke.root()["frame"].setValue(1001)
    write_to_read.write_to_read(group)

    # No second dialog: the media was found this time.
    assert len(dialogs) == 1
    read_nodes = nuke.allNodes("Read")
    assert len(read_nodes) == 1
    read = read_nodes[0]
    assert read["label"].value() == ""
    assert read["first"].value() == 1001
    assert read["last"].value() == 1010


def test_missing_single_file_prepares_read(dialogs, frame_range, tmp_path):
    movie = _posix(tmp_path / "missing.mov")
    group = _new_group_with_write(movie)

    write_to_read.write_to_read(group)

    assert len(dialogs) == 1
    read_nodes = nuke.allNodes("Read")
    assert len(read_nodes) == 1
    assert "missing.mov" in read_nodes[0]["file"].value()
    assert read_nodes[0]["label"].value() == write_to_read.PREPARED_LABEL


def test_prepared_deep_read(dialogs, frame_range, tmp_path):
    pattern = _pattern(tmp_path / "not_rendered_yet", name="renderDeep")
    group = _new_group_with_deep_write(pattern)

    write_to_read.write_to_read(group)

    assert len(dialogs) == 1
    deep_reads = nuke.allNodes("DeepRead")
    assert len(deep_reads) == 1
    assert "not_rendered_yet" in deep_reads[0]["file"].value()
    assert deep_reads[0]["label"].value() == write_to_read.PREPARED_LABEL


# -- Reading rendered media ------------------------------------------------


def test_rendered_sequence_is_detected(tmp_path):
    directory = tmp_path / "renders"
    _render(directory, range(1000, 1004))

    filepath, first_frame, last_frame = write_to_read.detect_file_on_disk(
        _pattern(directory),
        _posix(directory / "renderComp.1000.exr"),
        "",
        1001,
        False,
    )

    assert filepath.endswith("renderComp.####.exr")
    assert (first_frame, last_frame) == (1000, 1003)


def test_single_frame_sequence_is_detected(tmp_path):
    """One rendered frame with a padded pattern is still a sequence."""
    directory = tmp_path / "renders"
    _render(directory, [1001])

    filepath, first_frame, last_frame = write_to_read.detect_file_on_disk(
        _pattern(directory),
        _posix(directory / "renderComp.1001.exr"),
        "",
        1001,
        False,
    )

    assert filepath.endswith("renderComp.####.exr")
    assert (first_frame, last_frame) == (1001, 1001)


def test_prepared_read_is_promoted_for_single_frame(
    dialogs, frame_range, tmp_path
):
    """A single rendered frame must not break the promotion (IndexError)."""
    directory = tmp_path / "renders"
    pattern = _pattern(directory)
    group = _new_group_with_write(pattern)

    write_to_read.write_to_read(group)
    assert nuke.allNodes("Read")[0]["label"].value() == (
        write_to_read.PREPARED_LABEL
    )

    _render(directory, [1001])
    nuke.root()["frame"].setValue(1001)
    write_to_read.write_to_read(group)

    read_nodes = nuke.allNodes("Read")
    assert len(read_nodes) == 1
    read = read_nodes[0]
    assert read["label"].value() == ""
    assert (read["first"].value(), read["last"].value()) == (1001, 1001)


def test_single_file_is_read(dialogs, frame_range, tmp_path):
    movie = tmp_path / "movie.mov"
    movie.write_text("")
    group = _new_group_with_write(_posix(movie))

    write_to_read.write_to_read(group)

    assert dialogs == []
    read_nodes = nuke.allNodes("Read")
    assert len(read_nodes) == 1
    assert read_nodes[0]["file"].value() == _posix(movie)
    assert read_nodes[0]["label"].value() == ""


def test_project_directory_none_does_not_raise(tmp_path):
    """Issue #427: a `None` project directory used to reach clique."""
    directory = tmp_path / "renders"
    _render(directory, range(1000, 1002))

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
