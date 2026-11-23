"""Tests for the render path of a Write node.

A movie is one file for the whole render, so its path must not have a frame
token, even when the render path template has one. An image sequence keeps
the token, one file per frame (#440, YN-1299).
"""

import os

import nuke
import pytest

from ayon_core.lib import StringTemplate
from ayon_nuke.api import lib

FIRST_FRAME = 1001
LAST_FRAME = 1003

TEMPLATE = (
    "{work}/renders/nuke/{product[name]}/{product[name]}.{frame}.{ext}"
)


@pytest.fixture
def frame_range():
    """Set a workfile frame range and return it."""
    root = nuke.root()
    root["first_frame"].setValue(FIRST_FRAME)
    root["last_frame"].setValue(LAST_FRAME)
    return FIRST_FRAME, LAST_FRAME


def _posix(path):
    """Nuke stores and evaluates file paths with forward slashes."""
    return str(path).replace("\\", "/")


def _write_node(path, file_type):
    nuke.endGroup()
    source = nuke.createNode(
        "CheckerBoard2", "format square_256", inpanel=False
    )
    node = nuke.createNode("Write", inpanel=False)
    node.setInput(0, source)
    node["file"].setValue(_posix(path))
    node["file_type"].setValue(file_type)
    return node


def _render_path(template, ext, work):
    """Format the template the way the write creator does."""
    data = {
        "work": _posix(work),
        "product": {"name": "renderCompMovie"},
        "frame": "####",
        "ext": ext,
    }
    return StringTemplate(
        lib.get_render_path_template(template, ext)
    ).format_strict(data)


# -- Render path template ----------------------------------------------------


@pytest.mark.parametrize("template, expected", [
    # Dot separated frame token, as in the default template
    ("{work}/nuke/{product[name]}.{frame}.{ext}",
     "{work}/nuke/{product[name]}.{ext}"),
    # Underscore separated, keeps one separator
    ("{work}/nuke/{product[name]}_v{version}/{product[name]}_{frame}.{ext}",
     "{work}/nuke/{product[name]}_v{version}/{product[name]}.{ext}"),
    # Frame token at the end of the path
    ("{work}/nuke/{product[name]}.{frame}", "{work}/nuke/{product[name]}"),
    # No frame token at all
    ("{work}/nuke/{product[name]}.{ext}",
     "{work}/nuke/{product[name]}.{ext}"),
])
def test_movie_path_template_has_no_frame_token(template, expected):
    assert lib.get_render_path_template(template, "mov") == expected


@pytest.mark.parametrize("extension", ["exr", "dpx", "png"])
def test_image_path_template_keeps_the_frame_token(extension):
    template = "{work}/nuke/{product[name]}.{frame}.{ext}"

    assert lib.get_render_path_template(template, extension) == template
    assert lib.get_render_path_template(template, "." + extension) == template


# -- Rendered files ----------------------------------------------------------


def test_movie_path_formats_to_one_file(frame_range, tmp_path):
    path = _render_path(TEMPLATE, "mov", tmp_path)

    assert path == _posix(
        tmp_path / "renders/nuke/renderCompMovie/renderCompMovie.mov"
    )


def test_movie_path_is_the_same_for_every_frame(frame_range, tmp_path):
    """This is why a movie is collected as one file."""
    path = _render_path(TEMPLATE, "mov", tmp_path)
    write_node = _write_node(path, "mov")

    evaluated = {
        write_node["file"].evaluate(frame)
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    }

    assert evaluated == {path}


def test_image_path_changes_per_frame(frame_range, tmp_path):
    path = _render_path(TEMPLATE, "exr", tmp_path)
    write_node = _write_node(path, "exr")

    evaluated = {
        write_node["file"].evaluate(frame)
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    }

    assert evaluated == {
        path.replace("####", str(frame))
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    }


def test_movie_render_writes_one_file(frame_range, tmp_path):
    directory = tmp_path / "renders"
    directory.mkdir()
    write_node = _write_node(directory / "renderCompMovie.mov", "mov")

    nuke.execute(write_node.name(), FIRST_FRAME, LAST_FRAME)

    assert os.listdir(directory) == ["renderCompMovie.mov"]


def test_sequence_render_writes_one_file_per_frame(frame_range, tmp_path):
    directory = tmp_path / "renders"
    directory.mkdir()
    write_node = _write_node(directory / "renderCompMovie.####.exr", "exr")

    nuke.execute(write_node.name(), FIRST_FRAME, LAST_FRAME)

    assert os.listdir(directory) == [
        f"renderCompMovie.{frame}.exr"
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    ]
