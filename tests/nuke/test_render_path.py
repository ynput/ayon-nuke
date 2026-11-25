"""Tests for the render path of a Write node.

A movie is one file for the whole render, so its path must not have a frame
token, even when the render path template has one. An image sequence keeps
the token, one file per frame (#440, YN-1299).
"""

import logging
import os

import clique
import nuke
import pytest

from ayon_core.lib import StringTemplate
from ayon_nuke.api import lib
from ayon_nuke.api.plugin import ExporterReviewLut, ExporterReviewMov

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

    assert sorted(os.listdir(directory)) == [
        f"renderCompMovie.{frame}.exr"
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    ]


def test_intermediate_image_sequence_preserves_frame_token(tmp_path):
    source_files = [
        f"renderCompMovie.{frame}.exr"
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    ]
    collections, remainder = clique.assemble(source_files)

    assert not remainder
    assert len(collections) == 1

    class Extractor:
        log = logging.getLogger(__name__)
        viewer_lut_raw = False

    class Context:
        data = {}

    class Instance:
        context = Context()
        data = {
            "path": str(tmp_path / source_files[0]),
            "stagingDir": str(tmp_path),
            "collection": collections[0],
            "colorspace": "linear",
            "color_channels": "rgba",
            "anatomyData": {},
            "frameStartHandle": FIRST_FRAME,
            "frameEndHandle": LAST_FRAME,
        }

    exporter = ExporterReviewMov(
        Extractor,
        Instance,
        name="png",
        write_knobs={"custom": [], "file_type": "png"},
    )

    assert exporter.file == "renderCompMovie.png.#.png"
    assert lib.get_filenames_without_hash(
        exporter.file, FIRST_FRAME, LAST_FRAME
    ) == [
        f"renderCompMovie.png.{frame}.png"
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    ]
    exporter.get_representation_data()
    assert exporter.data["representations"][0]["files"] == [
        f"renderCompMovie.png.{frame}.png"
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    ]


def test_intermediate_image_sequence_generates_token_without_source_token(
    tmp_path,
):
    class Extractor:
        log = logging.getLogger(__name__)
        viewer_lut_raw = False

    class Context:
        data = {}

    class Instance:
        context = Context()
        data = {
            "path": str(tmp_path / "renderCompMovie.mov"),
            "stagingDir": str(tmp_path),
            "colorspace": "linear",
            "color_channels": "rgba",
            "anatomyData": {},
            "frameStartHandle": FIRST_FRAME,
            "frameEndHandle": LAST_FRAME,
        }

    exporter = ExporterReviewMov(
        Extractor,
        Instance,
        name="png",
        write_knobs={"custom": [], "file_type": "png"},
    )

    assert exporter.file == "renderCompMovie.png.####.png"
    assert lib.get_filenames_without_hash(
        exporter.file, FIRST_FRAME, LAST_FRAME
    ) == [
        f"renderCompMovie.png.{frame}.png"
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    ]
    exporter.get_representation_data()
    assert exporter.data["representations"][0]["files"] == [
        f"renderCompMovie.png.{frame}.png"
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    ]


def test_intermediate_movie_preserves_suffix_after_frame_token(tmp_path):
    class Extractor:
        log = logging.getLogger(__name__)
        viewer_lut_raw = False

    class Context:
        data = {}

    class Instance:
        context = Context()
        data = {
            "path": str(tmp_path / "renderCompMovie.####.left.exr"),
            "stagingDir": str(tmp_path),
            "colorspace": "linear",
            "color_channels": "rgba",
            "anatomyData": {},
            "frameStartHandle": FIRST_FRAME,
            "frameEndHandle": LAST_FRAME,
        }

    exporter = ExporterReviewMov(
        Extractor,
        Instance,
        name="review",
        write_knobs={"custom": [], "file_type": "mov"},
    )

    assert exporter.file == "renderCompMovie.review.left.mov"

    lut_exporter = ExporterReviewLut(
        Extractor,
        Instance,
        name="lut",
        ext="cube",
    )

    assert lut_exporter.file == "renderCompMovie.lut.left.cube"


def test_intermediate_image_sequence_parses_printf_token_without_collection(
    tmp_path,
):
    class Extractor:
        log = logging.getLogger(__name__)
        viewer_lut_raw = False

    class Context:
        data = {}

    class Instance:
        context = Context()
        data = {
            "path": str(tmp_path / "renderCompMovie.%04d.exr"),
            "stagingDir": str(tmp_path),
            "colorspace": "linear",
            "color_channels": "rgba",
            "anatomyData": {},
            "frameStartHandle": FIRST_FRAME,
            "frameEndHandle": LAST_FRAME,
        }

    exporter = ExporterReviewMov(
        Extractor,
        Instance,
        name="png",
        write_knobs={"custom": [], "file_type": "png"},
    )

    assert exporter.file == "renderCompMovie.png.####.png"
    assert lib.get_filenames_without_hash(
        exporter.file, FIRST_FRAME, LAST_FRAME
    ) == [
        f"renderCompMovie.png.{frame}.png"
        for frame in range(FIRST_FRAME, LAST_FRAME + 1)
    ]
