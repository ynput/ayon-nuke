"""Tests for the `Read From Rendered` and `Clear Rendered` buttons.

The buttons of AYON's render groups call `ayon_nuke.api.utils`. Render
groups made before (#427, #428, #429) keep their old commands, which go
through `ayon_nuke/startup/write_to_read.py` and `clear_rendered.py`.
"""

import os

import nuke
import pytest

from ayon_nuke.api import lib, utils

STARTUP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(utils.__file__)), "startup"
)

#: Button commands stored in workfiles by earlier versions of AYON.
OLD_WRITE_TO_READ = (
    "import write_to_read;"
    "write_to_read.write_to_read(nuke.thisNode(), allow_relative=False)"
)
OLD_CLEAR_RENDERED = (
    "import clear_rendered;"
    "clear_rendered.clear_rendered_from_node(nuke.thisNode())"
)
OLDER_CLEAR_RENDERED = (
    "import clear_rendered;clear_rendered.clear_rendered('{}')"
)


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


@pytest.fixture
def startup_on_path(monkeypatch):
    """Make the startup modules importable, as Nuke's NUKE_PATH does."""
    monkeypatch.syspath_prepend(STARTUP_DIR)


def _posix(path):
    """Nuke stores and evaluates file paths with forward slashes."""
    return str(path).replace("\\", "/")


def _as_hashes(path):
    """Nuke stores a `####` file knob value as `%04d`."""
    return path.replace("%04d", "####")


def _pattern(directory, name="renderComp"):
    return _posix(directory / f"{name}.####.exr")


def _render(directory, frames, name="renderComp"):
    """Create fake rendered frames in `directory`."""
    directory.mkdir(parents=True, exist_ok=True)
    for frame in frames:
        (directory / f"{name}.{frame:04d}.exr").write_text("")


def _new_group(write_pattern, node_class="Write", use_limit=False,
               first_frame=None, last_frame=None):
    """Create a Group with a single Write node using `write_pattern`."""
    nuke.endGroup()
    group = nuke.createNode("Group", "name renderGroup", inpanel=False)
    nuke.endGroup()
    with group:
        write_node = nuke.createNode(node_class, inpanel=False)
        write_node["file"].setValue(write_pattern)
        if use_limit:
            write_node["use_limit"].setValue(True)
            write_node["first"].setValue(first_frame)
            write_node["last"].setValue(last_frame)
    return group


def _add_button(group, name, command):
    knob = nuke.PyScript_Knob(name, name, command)
    group.addKnob(knob)
    return knob


# -- Frame range -------------------------------------------------------------


def test_write_frame_range_uses_workfile_range(frame_range, tmp_path):
    group = _new_group(_pattern(tmp_path))
    write_node = nuke.allNodes("Write", group=group)[0]

    assert utils.get_write_frame_range(write_node) == frame_range


def test_write_frame_range_uses_limit(frame_range, tmp_path):
    group = _new_group(
        _pattern(tmp_path), use_limit=True, first_frame=1005, last_frame=1010
    )
    write_node = nuke.allNodes("Write", group=group)[0]

    assert utils.get_write_frame_range(write_node) == (1005, 1010)


# -- Nothing rendered yet ----------------------------------------------------


def test_missing_render_folder_creates_read(dialogs, frame_range, tmp_path):
    first_frame, last_frame = frame_range
    pattern = _pattern(tmp_path / "not_rendered_yet")
    group = _new_group(pattern)

    read = utils.read_from_rendered(group)

    assert len(dialogs) == 1
    assert "Nothing is rendered yet" in dialogs[0]
    assert "not_rendered_yet" in dialogs[0]
    assert nuke.allNodes("Read") == [read]
    assert _as_hashes(read["file"].value()) == pattern
    assert (read["first"].value(), read["last"].value()) == frame_range


def test_missing_render_uses_write_frame_range(
    dialogs, frame_range, tmp_path
):
    group = _new_group(
        _pattern(tmp_path / "not_rendered_yet"),
        use_limit=True, first_frame=1005, last_frame=1010,
    )

    read = utils.read_from_rendered(group)

    assert (read["first"].value(), read["last"].value()) == (1005, 1010)


def test_missing_deep_render_creates_deep_read(
    dialogs, frame_range, tmp_path
):
    pattern = _pattern(tmp_path / "not_rendered_yet", name="renderDeep")
    group = _new_group(pattern, node_class="DeepWrite")

    read = utils.read_from_rendered(group)

    assert len(dialogs) == 1
    assert read.Class() == "DeepRead"
    assert _as_hashes(read["file"].value()) == pattern


# -- Rendered images ---------------------------------------------------------


def test_rendered_sequence_ignores_playhead(dialogs, frame_range, tmp_path):
    """The render is found even when the playhead is past the last frame."""
    directory = tmp_path / "renders"
    _render(directory, range(1001, 1011))
    group = _new_group(_pattern(directory))
    nuke.root()["frame"].setValue(1030)

    read = utils.read_from_rendered(group)

    assert dialogs == []
    assert _as_hashes(read["file"].value()) == _pattern(directory)
    assert (read["first"].value(), read["last"].value()) == (1001, 1010)
    assert read["frame_mode"].value() == "start at"
    assert read["frame"].value() == "1001"


def test_frames_outside_render_range_are_ignored(
    dialogs, frame_range, tmp_path
):
    directory = tmp_path / "renders"
    _render(directory, range(990, 1004))
    group = _new_group(_pattern(directory))

    read = utils.read_from_rendered(group)

    assert (read["first"].value(), read["last"].value()) == (1001, 1003)


def test_single_rendered_frame_is_read(dialogs, frame_range, tmp_path):
    """A single rendered frame used to raise `IndexError`."""
    directory = tmp_path / "renders"
    _render(directory, [1001])
    group = _new_group(_pattern(directory))

    read = utils.read_from_rendered(group)

    assert dialogs == []
    assert (read["first"].value(), read["last"].value()) == (1001, 1001)


def test_still_image_without_frame_token(dialogs, frame_range, tmp_path):
    still = tmp_path / "still.exr"
    still.write_text("")
    group = _new_group(_posix(still))

    read = utils.read_from_rendered(group)

    assert dialogs == []
    assert read["file"].value() == _posix(still)
    assert (read["first"].value(), read["last"].value()) == (1001, 1001)


def test_colorspace_is_copied_by_name(dialogs, frame_range, tmp_path):
    directory = tmp_path / "renders"
    _render(directory, [1001])
    group = _new_group(_pattern(directory))
    write_node = nuke.allNodes("Write", group=group)[0]
    write_node["colorspace"].setValue("sRGB")

    read = utils.read_from_rendered(group)

    assert read["colorspace"].value() == "sRGB"


# -- Movies (single video file) ----------------------------------------------


def _render_movie(group):
    """Render a real movie with the group's Write node, 1001-1010."""
    with group:
        write_node = nuke.allNodes("Write")[0]
        source = nuke.createNode(
            "CheckerBoard2", "format square_256", inpanel=False
        )
        write_node.setInput(0, source)
        write_node["file_type"].setValue("mov")
        nuke.execute(write_node, 1001, 1010)


@pytest.mark.parametrize("name", ["renderComp.####.mov", "renderComp.mov"])
def test_rendered_movie_is_read(dialogs, frame_range, tmp_path, name):
    """The movie file is read with its own range, starting at 1001.

    With a frame token in the path Nuke writes one file named after the
    first frame, `renderComp.1001.mov`.
    """
    group = _new_group(
        _posix(tmp_path / name),
        use_limit=True, first_frame=1001, last_frame=1010,
    )
    _render_movie(group)
    nuke.root()["frame"].setValue(1005)

    read = utils.read_from_rendered(group)

    assert dialogs == []
    expected = name.replace("####", "1001")
    assert read["file"].value() == _posix(tmp_path / expected)
    assert (read["first"].value(), read["last"].value()) == (1, 10)
    assert read["frame_mode"].value() == "start at"
    assert read["frame"].value() == "1001"


def test_missing_movie_creates_read(dialogs, frame_range, tmp_path):
    first_frame, last_frame = frame_range
    group = _new_group(_posix(tmp_path / "missing.####.mov"))

    read = utils.read_from_rendered(group)

    assert len(dialogs) == 1
    assert read["file"].value() == _posix(tmp_path / "missing.1001.mov")
    assert (read["first"].value(), read["last"].value()) == (
        1, last_frame - first_frame + 1
    )
    assert read["frame"].value() == str(first_frame)


# -- Buttons, new and stored in older workfiles ------------------------------


def test_new_read_button(dialogs, frame_range, tmp_path):
    directory = tmp_path / "renders"
    _render(directory, range(1001, 1004))
    group = _new_group(_pattern(directory))
    lib.add_button_write_to_read(group)

    assert "ayon_nuke.api.utils" in group["createReadNode"].value()
    group["createReadNode"].execute()

    assert len(nuke.allNodes("Read")) == 1


def test_old_read_button_still_works(
    dialogs, frame_range, tmp_path, startup_on_path
):
    directory = tmp_path / "renders"
    _render(directory, range(1001, 1004))
    group = _new_group(_pattern(directory))
    _add_button(group, "createReadNode", OLD_WRITE_TO_READ).execute()

    read_nodes = nuke.allNodes("Read")
    assert len(read_nodes) == 1
    read = read_nodes[0]
    assert (read["first"].value(), read["last"].value()) == (1001, 1003)


def test_new_clear_button(frame_range, tmp_path):
    directory = tmp_path / "renders"
    _render(directory, range(1001, 1004))
    group = _new_group(_pattern(directory))
    lib.add_button_clear_rendered(group)

    assert "ayon_nuke.api.utils" in group["clearRendered"].value()
    group["clearRendered"].execute()

    assert os.listdir(directory) == []


def test_read_is_created_next_to_nested_group(
    dialogs, frame_range, tmp_path
):
    directory = tmp_path / "renders"
    _render(directory, [1001])
    outer = nuke.createNode("Group", "name outer", inpanel=False)
    nuke.endGroup()
    with outer:
        group = nuke.createNode("Group", "name inner", inpanel=False)
        nuke.endGroup()
        with group:
            write_node = nuke.createNode("Write", inpanel=False)
            write_node["file"].setValue(_pattern(directory))
    lib.add_button_write_to_read(group)

    group["createReadNode"].execute()

    read_nodes = [node for node in outer.nodes() if node.Class() == "Read"]
    assert [node.fullName() for node in read_nodes] == ["outer.Read1"]
    assert nuke.allNodes("Read", group=group) == []


@pytest.mark.parametrize("command", ["from_node", "baked_path"])
def test_old_clear_buttons_still_work(
    frame_range, tmp_path, startup_on_path, command
):
    directory = tmp_path / "renders"
    _render(directory, range(1001, 1004))
    group = _new_group(_pattern(directory))
    if command == "from_node":
        value = OLD_CLEAR_RENDERED
    else:
        value = OLDER_CLEAR_RENDERED.format(_posix(directory))
    _add_button(group, "clearRendered", value).execute()

    assert os.listdir(directory) == []
