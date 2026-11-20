"""Tests of trait first loading.

Legacy representations (without traits) are converted to traits and must
load exactly as on `develop` branch - `develop_*` functions are copies of
the loader code on `develop` and are compared with the current loaders.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest

from _module_loader import load_api_module, load_load_plugin_module

ROOT = "/mnt/work"


class FakeAnatomy:
    roots = {"work": ROOT}

    def fill_root(self, path):
        return path.replace("{root[work]}", ROOT)


ANATOMY = FakeAnatomy()


def fake_get_representation_path(project_name, repre_entity, anatomy=None):
    """Fill representation template like ayon-core does."""
    return repre_entity["attrib"]["template"].format(
        root={"work": ROOT}, **repre_entity["context"])


@pytest.fixture(scope="module")
def load_traits():
    module = load_api_module("load_traits")
    module.get_representation_path = fake_get_representation_path
    return module


@pytest.fixture(scope="module")
def load_clip(load_traits):
    return load_load_plugin_module("load_clip", load_traits).LoadClip


@pytest.fixture(scope="module")
def load_image(load_traits):
    return load_load_plugin_module("load_image", load_traits).LoadImage


# --- develop branch loader code ----------------------------------------
from ayon_core.lib.transcoding import (  # noqa: E402
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)


def develop_get_frame_range(version_attributes):
    """`LoadClip._get_frame_range` on develop."""
    first = version_attributes.get("frameStart")
    last = version_attributes.get("frameEnd")
    if first is None or last is None:
        return None, None

    first -= version_attributes.get("handleStart") or 0
    last += version_attributes.get("handleEnd") or 0
    return first, last


def develop_clip_load_frame_range(context):
    """`LoadClip.load` frame range on develop."""
    repre_entity = context["representation"]
    version_attributes = context["version"]["attrib"]
    is_sequence = len(repre_entity["files"]) > 1
    first, last = develop_get_frame_range(version_attributes)

    slate_frames = repre_entity["data"].get("slateFrames", 0)
    extension = "." + repre_entity["context"]["ext"]
    files_count = len(repre_entity["files"])

    if first is not None and last is not None:
        if not is_sequence:
            duration = last - first
            first = 1
            last = first + duration
        if extension in VIDEO_EXTENSIONS:
            last += slate_frames
        elif extension in IMAGE_EXTENSIONS and files_count != 1:
            first -= slate_frames
    return first, last


def develop_clip_update_frame_range(context):
    """`LoadClip.update` frame range on develop."""
    repre_entity = context["representation"]
    is_sequence = len(repre_entity["files"]) > 1
    first, last = develop_get_frame_range(context["version"]["attrib"])
    if first is not None and last is not None and not is_sequence:
        duration = last - first
        first = 1
        last = first + duration
    return first, last


def develop_representation_with_hash_in_frame(repre_entity):
    """`LoadClip._representation_with_hash_in_frame` on develop."""
    new_repre_entity = deepcopy(repre_entity)
    context = new_repre_entity["context"]
    frame = context["frame"]
    hashed_frame = "#" * len(str(frame))
    if "{originalBasename}" in new_repre_entity["attrib"]["template"]:
        origin_basename = context["originalBasename"]
        context["originalBasename"] = origin_basename.replace(
            frame, hashed_frame
        )
    new_repre_entity["context"]["frame"] = hashed_frame
    return new_repre_entity


def develop_clip_path(context):
    """`LoadClip.load` / `update` file path on develop."""
    repre_entity = context["representation"]
    if len(repre_entity["files"]) > 1:
        repre_entity = develop_representation_with_hash_in_frame(
            repre_entity)
    return fake_get_representation_path(
        "test_project", repre_entity).replace("\\", "/")


def develop_clip_original_path(context):
    """`LoadClip.load` path for node type detection on develop."""
    return fake_get_representation_path(
        "test_project", context["representation"])


def develop_image_path(context, frame_number):
    """`LoadImage.load` file path on develop."""
    repre_entity = context["representation"]
    filepath = fake_get_representation_path("test_project", repre_entity)
    filepath = filepath.replace("\\", "/")
    frame = repre_entity["context"].get("frame")
    if frame:
        padding = len(frame)
        filepath = filepath.replace(
            frame, format(frame_number, "0{}".format(padding))
        )
    return filepath


def develop_colorspace(context):
    """`LoadClip._get_colorspace_data` on develop (without file rules)."""
    repre_data = context["representation"]["data"]
    colorspace = repre_data.get("colorspaceData", {}).get("colorspace")
    if not colorspace:
        colorspace = repre_data.get("colorspace")
    if not colorspace:
        colorspace = context["version"]["attrib"].get("colorSpace")
    return colorspace


# --- fixtures ------------------------------------------------------------
VERSION_ATTRIB = {
    "frameStart": 1001,
    "frameEnd": 1010,
    "handleStart": 2,
    "handleEnd": 3,
    "fps": 25.0,
    "colorSpace": "ACES - ACEScg",
    "source": "/work/sh010.nk",
}


def _context(repre_entity, version_attrib=None):
    if version_attrib is None:
        version_attrib = VERSION_ATTRIB
    return {
        "project": {"name": "test_project"},
        "version": {
            "id": "version-id",
            "version": 1,
            "attrib": dict(version_attrib),
            "data": {},
        },
        "representation": repre_entity,
    }


def _sequence_entity(
    frame_start=None,
    frame_end=1013,
    slate_frames=None,
    data=None,
    ext="exr",
    padding=4,
    original_basename=False,
):
    """Sequence with handles of `VERSION_ATTRIB` (and slate) in files."""
    if frame_start is None:
        frame_start = 999 - (slate_frames or 0)
    data = dict(data or {})
    if slate_frames is not None:
        data["slateFrames"] = slate_frames
    first_frame = f"{frame_start:0{padding}d}"
    context = {"ext": ext, "frame": first_frame, "representation": ext}
    template = "{root[work]}/sh010/render.{frame}.{ext}"
    if original_basename:
        context["originalBasename"] = f"plate_{first_frame}"
        template = "{root[work]}/sh010/{originalBasename}.{ext}"
    name = "plate" if original_basename else "render"
    return {
        "id": "repre-id",
        "name": ext,
        "attrib": {"template": template},
        "context": context,
        "files": [
            {"path": f"{{root[work]}}/sh010/{name}.{frame:0{padding}d}.{ext}"}
            for frame in range(frame_start, frame_end + 1)
        ],
        "data": data,
    }


def _single_file_entity(ext="mov", slate_frames=None, data=None, frame=None):
    data = dict(data or {})
    if slate_frames is not None:
        data["slateFrames"] = slate_frames
    context = {"ext": ext, "representation": ext}
    template = "{root[work]}/sh010/render.{ext}"
    filename = f"render.{ext}"
    if frame is not None:
        context["frame"] = frame
        template = "{root[work]}/sh010/render.{frame}.{ext}"
        filename = f"render.{frame}.{ext}"
    return {
        "id": "repre-id",
        "name": ext,
        "attrib": {"template": template},
        "context": context,
        "files": [{"path": f"{{root[work]}}/sh010/{filename}"}],
        "data": data,
    }


LEGACY_CONTEXTS = {
    "sequence": _context(_sequence_entity()),
    "sequence_slate": _context(_sequence_entity(slate_frames=1)),
    "sequence_no_handles_in_files": _context(_sequence_entity(1001, 1010)),
    "sequence_unpadded": _context(_sequence_entity(999, 1013, padding=1)),
    "sequence_original_basename": _context(
        _sequence_entity(original_basename=True)),
    "sequence_no_version_range": _context(_sequence_entity(), {}),
    "sequence_handles_none": _context(
        _sequence_entity(),
        dict(VERSION_ATTRIB, handleStart=None, handleEnd=None),
    ),
    "sequence_colorspace_data": _context(_sequence_entity(data={
        "colorspaceData": {"colorspace": "sRGB"}, "colorspace": "linear"})),
    "sequence_colorspace": _context(
        _sequence_entity(data={"colorspace": "linear"})),
    "movie": _context(_single_file_entity()),
    "movie_slate": _context(_single_file_entity(slate_frames=1)),
    "image": _context(_single_file_entity(ext="png")),
    "image_slate": _context(_single_file_entity(ext="png", slate_frames=1)),
    "single_frame": _context(_single_file_entity(ext="exr", frame="1001")),
    "movie_no_version_range": _context(_single_file_entity(), {}),
}


def _load(load_traits, context):
    return load_traits.LoadRepresentation.from_context(
        deepcopy(context), ANATOMY)


# --- legacy representations behave as on develop -------------------------
@pytest.mark.parametrize("name", list(LEGACY_CONTEXTS))
class TestLegacyMatchesDevelop:
    def test_converted(self, load_traits, name):
        assert _load(load_traits, LEGACY_CONTEXTS[name]).is_converted

    def test_clip_load_frame_range(self, load_traits, load_clip, name):
        context = LEGACY_CONTEXTS[name]
        load_repre = _load(load_traits, context)
        assert load_clip._get_frame_range(load_repre) == (
            develop_clip_load_frame_range(context))

    def test_clip_update_frame_range(self, load_traits, load_clip, name):
        context = LEGACY_CONTEXTS[name]
        load_repre = _load(load_traits, context)
        assert load_clip._get_frame_range(
            load_repre, legacy_slate=False
        ) == develop_clip_update_frame_range(context)

    def test_clip_path(self, load_traits, name):
        context = LEGACY_CONTEXTS[name]
        load_repre = _load(load_traits, context)
        assert load_repre.get_file_path() == develop_clip_path(context)
        assert load_repre.get_first_file_path() == (
            develop_clip_original_path(context))

    @pytest.mark.parametrize("frame_number", [1001, 1005])
    def test_image_path(self, load_traits, load_image, name, frame_number):
        context = LEGACY_CONTEXTS[name]
        load_repre = _load(load_traits, context)
        loader = mock.MagicMock()
        assert load_image._get_filepath(
            loader, load_repre, frame_number
        ) == develop_image_path(context, frame_number)
        loader.log.warning.assert_not_called()

    def test_version_attributes(self, load_traits, name):
        context = LEGACY_CONTEXTS[name]
        attributes = _load(load_traits, context).version_attributes
        assert attributes == context["version"]["attrib"]
        assert attributes is not context["version"]["attrib"]

    def test_colorspace(self, load_traits, name):
        context = LEGACY_CONTEXTS[name]
        assert _load(load_traits, context).colorspace == (
            develop_colorspace(context))

    def test_slate_frames(self, load_traits, name):
        context = LEGACY_CONTEXTS[name]
        assert _load(load_traits, context).slate_frames == (
            context["representation"]["data"].get("slateFrames", 0))


class TestLegacyConversion:
    def test_traits(self, load_traits):
        t = load_traits
        representation = _load(
            t, LEGACY_CONTEXTS["sequence_slate"]).representation

        assert t.is_sequence(representation) is True
        assert t.get_file_count(representation) == 16
        assert t.get_slate_frames(representation) == 1
        assert t.get_colorspace(representation) == "ACES - ACEScg"
        frame_range = t.get_frame_range(representation)
        assert (frame_range.frame_start, frame_range.frame_end) == (
            998, 1013)
        assert (
            frame_range.content_frame_start,
            frame_range.content_frame_end,
        ) == (1001, 1010)
        assert t.get_file_path(representation, ANATOMY) == (
            f"{ROOT}/sh010/render.####.exr")

    def test_padding_from_context_frame(self, load_traits):
        t = load_traits
        representation = _load(
            t, LEGACY_CONTEXTS["sequence_unpadded"]).representation
        assert t.get_file_path(representation, ANATOMY) == (
            f"{ROOT}/sh010/render.###.exr")


# --- representations published with traits --------------------------------
def _with_traits(load_traits, repre_entity, traits):
    """Entity with traits stored like `IntegrateTraits` stores them."""
    from ayon_core.pipeline.traits import prepare_for_json

    representation = load_traits.Representation(
        name=repre_entity["name"], traits=traits)
    repre_entity = dict(repre_entity)
    repre_entity["traits"] = representation.traits_as_dict(
        persistent_only=True)
    return prepare_for_json(repre_entity)


def _published_sequence_traits(load_traits, rootless=True):
    t = load_traits
    traits = [
        t.FileLocations(file_paths=[
            t.FileLocation(
                file_path=Path(f"/old/root/sh010/render.{frame:04d}.exr"))
            for frame in range(998, 1014)
        ]),
        t.Sequence(frame_padding=4),
        t.FrameRanged(
            frame_start=998, frame_end=1013, frame_rate_numerator=24),
        t.Handles(inclusive=True, frame_start_handle=2, frame_end_handle=3),
        t.Slate(frames=1),
        t.ColorManaged(color_space="ACES - ACES2065-1"),
    ]
    if rootless:
        traits.append(t.RootlessLocation(rootless_path="{root[work]}/sh010"))
    return traits


class TestTraitRepresentation:
    def test_values_from_traits(self, load_traits, load_clip):
        repre_entity = _with_traits(
            load_traits,
            # legacy data differ - traits have priority
            _sequence_entity(data={"colorspace": "linear"}),
            _published_sequence_traits(load_traits),
        )
        load_repre = _load(load_traits, _context(repre_entity))

        assert load_repre.is_converted is False
        assert load_repre.colorspace == "ACES - ACES2065-1"
        assert load_repre.slate_frames == 1
        # range of files - slate and handles included
        assert load_clip._get_frame_range(load_repre) == (998, 1013)
        assert load_clip._get_frame_range(
            load_repre, legacy_slate=False) == (998, 1013)
        assert load_repre.get_file_path() == (
            f"{ROOT}/sh010/render.####.exr")
        assert load_repre.get_file_path(frame=1001) == (
            f"{ROOT}/sh010/render.1001.exr")

        attributes = load_repre.version_attributes
        assert attributes["frameStart"] == 1001
        assert attributes["frameEnd"] == 1010
        assert attributes["fps"] == 24.0
        assert attributes["colorSpace"] == "ACES - ACES2065-1"
        assert attributes["source"] == "/work/sh010.nk"

    def test_handles_not_in_files(self, load_traits, load_clip):
        t = load_traits
        traits = _published_sequence_traits(t)
        traits[3] = t.Handles(
            inclusive=False, frame_start_handle=2, frame_end_handle=3)
        traits[2] = t.FrameRanged(frame_start=1000, frame_end=1010)
        repre_entity = _with_traits(t, _sequence_entity(), traits)
        load_repre = _load(t, _context(repre_entity))
        assert load_clip._get_frame_range(load_repre) == (1000, 1010)

    def test_files_without_rootless_location_from_entity(self, load_traits):
        repre_entity = _with_traits(
            load_traits,
            _sequence_entity(slate_frames=1),
            _published_sequence_traits(load_traits, rootless=False),
        )
        load_repre = _load(load_traits, _context(repre_entity))
        # publish time paths are replaced with entity files
        assert load_repre.get_file_path(frame=1001) == (
            f"{ROOT}/sh010/render.1001.exr")

    def test_missing_traits_completed_from_legacy(
        self, load_traits, load_clip
    ):
        t = load_traits
        # movie published with traits without frame range
        repre_entity = _with_traits(
            t,
            _single_file_entity(slate_frames=1),
            [t.Slate(frames=1), t.ColorManaged(color_space="sRGB")],
        )
        load_repre = _load(t, _context(repre_entity))

        assert load_repre.is_converted is False
        assert load_repre.colorspace == "sRGB"
        assert load_repre.get_file_path() == f"{ROOT}/sh010/render.mov"
        # movie with slate is one frame longer
        assert load_clip._get_frame_range(load_repre) == (
            develop_clip_load_frame_range(LEGACY_CONTEXTS["movie_slate"]))

    def test_completion_keeps_trait_groups(self, load_traits):
        t = load_traits
        representation = t.Representation(name="exr", traits=[
            t.FrameRanged(frame_start=1, frame_end=10),
        ])
        source = t.Representation(name="exr", traits=[
            t.FrameRanged(frame_start=100, frame_end=200),
            t.Handles(inclusive=True, frame_start_handle=5),
            t.Slate(frames=1),
        ])
        added = t.complete_representation(representation, source)

        assert added == [t.Slate]
        assert not representation.contains_trait(t.Handles)
        assert representation.get_trait(t.FrameRanged).frame_start == 1

    def test_broken_traits_load_as_legacy(self, load_traits, load_clip):
        repre_entity = _sequence_entity(slate_frames=1)
        repre_entity["traits"] = "{not valid json"
        context = _context(repre_entity)
        load_repre = _load(load_traits, context)

        assert load_repre.is_converted is True
        assert load_clip._get_frame_range(load_repre) == (
            develop_clip_load_frame_range(context))

    def test_deep(self, load_traits):
        t = load_traits
        repre_entity = _with_traits(
            t,
            _sequence_entity(),
            _published_sequence_traits(t) + [t.Deep()],
        )
        load_repre = _load(t, _context(repre_entity))
        assert load_repre.is_deep is True
