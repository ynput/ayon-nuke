"""Helpers for publishing and loading trait based representations in Nuke.

Trait representations are used only when enabled in settings
(`CollectNukeWrites.use_trait_representations`) and only for render
targets processed inside Nuke ("local" and "frames"). Farm targets create
their representations on the farm and keep using legacy dictionaries.

An instance uses either trait representations or legacy dictionaries,
never both - `Integrate` in ayon-core skips instances with trait
representations and `IntegrateTraits` integrates them.

Loaders use traits stored on representation entities (frame range,
handles, slate, colorspace) when they are available and fall back to
version attributes and representation data of legacy representations.
"""
from __future__ import annotations

import copy
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import nuke

from ayon_core.pipeline.colorspace import (
    set_colorspace_data_to_representation,
)
from ayon_core.pipeline.load import (
    get_representation_path,
    get_representation_traits,
)
from ayon_core.pipeline.publish import get_trait_representations
from ayon_core.pipeline.publish.review_utils import DEFAULT_IMAGE_EXTS
from ayon_core.pipeline.publish.trait_conversion import (
    color_managed_from_colorspace_data,
    sequence_traits_from_files,
)
from ayon_core.pipeline.traits import (
    ColorManaged,
    FileLocation,
    FileLocations,
    FrameRanged,
    Handles,
    Image,
    MimeType,
    Persistent,
    PixelBased,
    Representation,
    Sequence,
    Slate,
    SourceApplication,
    Tagged,
    get_frame_range_data,
)

# Render targets which create representations inside Nuke
TRAIT_RENDER_TARGETS = {"local", "frames"}
INSTANCE_DATA_KEY = "useTraitRepresentations"


def _get_instance_value(instance, key: str, default=None):
    """Value from instance data with fallback to context data."""
    value = instance.data.get(key)
    if value is None:
        value = instance.context.data.get(key, default)
    return value


def uses_trait_representations(instance) -> bool:
    """Instance publishes trait representations instead of legacy dicts."""
    return bool(instance.data.get(INSTANCE_DATA_KEY))


def get_representation_filenames(representation: Representation) -> list:
    """File names (without directory) of a trait representation."""
    if representation.contains_trait(FileLocations):
        return [
            Path(file_location.file_path).name
            for file_location in representation.get_trait(
                FileLocations).file_paths
        ]
    if representation.contains_trait(FileLocation):
        return [
            Path(representation.get_trait(FileLocation).file_path).name
        ]
    return []


def find_representation_by_filename(
    instance, filename: str
) -> Optional[Representation]:
    """Find trait representation containing file with given name."""
    for representation in get_trait_representations(instance):
        if filename in get_representation_filenames(representation):
            return representation
    return None


def set_file_traits(
    representation: Representation,
    output_dir: str,
    filenames: list,
    fps: Optional[float] = None,
) -> None:
    """Set (or replace) file and frame related traits.

    `FrameRanged` is computed from the files themselves, so it also
    covers e.g. a slate frame added before the first frame.
    """
    for trait in (FileLocation, FileLocations, FrameRanged, Sequence):
        if representation.contains_trait(trait):
            representation.remove_trait(trait)

    paths = [Path(output_dir) / filename for filename in filenames]
    if len(paths) == 1:
        representation.add_trait(FileLocation(file_path=paths[0]))
        return

    representation.add_trait(FileLocations(file_paths=[
        FileLocation(file_path=path) for path in paths
    ]))
    sequence_traits = sequence_traits_from_files(paths, fps=fps)
    if sequence_traits is not None:
        representation.add_traits(list(sequence_traits))


def create_write_representation(
    instance,
    write_node,
    filenames: list,
    output_dir: str,
    colorspace: Optional[str] = None,
    tags: Optional[list] = None,
) -> Representation:
    """Create trait representation for files rendered by a write node.

    Args:
        instance (pyblish.api.Instance): Publish instance.
        write_node (nuke.Node): Write node that produced the files.
        filenames (list[str]): File names in `output_dir`.
        output_dir (str): Directory with rendered files.
        colorspace (Optional[str]): Colorspace of the files.
        tags (Optional[list[str]]): Representation tags.

    Returns:
        Representation: Trait based representation.

    """
    filenames = sorted(filenames)
    ext = os.path.splitext(filenames[0])[1].lstrip(".").lower()
    context = instance.context

    representation = Representation(name=ext, traits=[
        Tagged(tags=list(tags or [])),
        Persistent(),
        PixelBased(
            display_window_width=write_node.width(),
            display_window_height=write_node.height(),
            pixel_aspect_ratio=float(write_node.pixelAspect()),
        ),
        SourceApplication(
            application="nuke",
            version=nuke.NUKE_VERSION_STRING,
            host_name=context.data.get("hostName"),
        ),
    ])
    set_file_traits(
        representation,
        output_dir,
        filenames,
        fps=_get_instance_value(instance, "fps"),
    )

    if len(filenames) > 1:
        # Frame range from the write node includes handles
        # - collectors may run before handles are set on instance
        representation.add_trait(Handles(
            inclusive=True,
            frame_start_handle=_get_instance_value(instance, "handleStart", 0),
            frame_end_handle=_get_instance_value(instance, "handleEnd", 0),
        ))

    mime_type, _ = mimetypes.guess_type(f"file.{ext}")
    if mime_type:
        representation.add_trait(MimeType(mime_type=mime_type))
    if ext in DEFAULT_IMAGE_EXTS:
        representation.add_trait(Image())

    # Resolve colorspace data the same way as for legacy dicts
    colorspace_shim = {
        "ext": ext,
        "files": filenames if len(filenames) > 1 else filenames[0],
    }
    set_colorspace_data_to_representation(
        colorspace_shim, context.data, colorspace=colorspace
    )
    color_managed = color_managed_from_colorspace_data(
        colorspace_shim.get("colorspaceData")
    )
    if color_managed is not None:
        representation.add_trait(color_managed)

    return representation


def add_tag(representation: Representation, tag: str) -> None:
    """Add tag to representation `Tagged` trait."""
    tags = []
    if representation.contains_trait(Tagged):
        tags = list(representation.get_trait(Tagged).tags)
        representation.remove_trait(Tagged)
    if tag not in tags:
        tags.append(tag)
    representation.add_trait(Tagged(tags=tags))


@dataclass
class LoadTraitsData:
    """Data for loaders resolved from representation traits.

    Attributes:
        representation (Representation): Representation with traits.
        is_sequence (bool): Representation is a sequence of frames.
        frame_padding (Optional[int]): Padding of frame numbers in file
            names of a sequence.
        frame_start (Optional[int]): First frame of the files (includes
            slate and handles).
        frame_end (Optional[int]): Last frame of the files (includes
            handles).
        content_frame_start (Optional[int]): First frame of the content
            without slate and handles.
        content_frame_end (Optional[int]): Last frame of the content
            without handles.
        handle_start (Optional[int]): Handle frames at the start.
        handle_end (Optional[int]): Handle frames at the end.
        handles_in_files (bool): Files contain the handle frames.
        slate_frames (int): Slate frames at the start of the content.
        fps (Optional[float]): Frames per second.
        colorspace (Optional[str]): Colorspace of the files.

    """
    representation: Representation
    is_sequence: bool = False
    frame_padding: Optional[int] = None
    frame_start: Optional[int] = None
    frame_end: Optional[int] = None
    content_frame_start: Optional[int] = None
    content_frame_end: Optional[int] = None
    handle_start: Optional[int] = None
    handle_end: Optional[int] = None
    handles_in_files: bool = False
    slate_frames: int = 0
    fps: Optional[float] = None
    colorspace: Optional[str] = None


def get_load_traits_data(repre_entity: dict) -> Optional[LoadTraitsData]:
    """Get data for loaders from traits of representation entity.

    Args:
        repre_entity (dict): Representation entity.

    Returns:
        Optional[LoadTraitsData]: Data resolved from traits or None if
            the representation was not published with traits.

    """
    representation = get_representation_traits(repre_entity)
    if representation is None:
        return None

    data = LoadTraitsData(representation=representation)
    if representation.contains_trait(FileLocations):
        file_paths = representation.get_trait(FileLocations).file_paths
        data.is_sequence = len(file_paths) > 1

    if representation.contains_trait(Sequence):
        data.is_sequence = True
        data.frame_padding = representation.get_trait(Sequence).frame_padding

    frame_range = get_frame_range_data(representation)
    if frame_range is not None:
        data.frame_start = frame_range.frame_start
        data.frame_end = frame_range.frame_end
        data.handle_start = frame_range.handle_start
        data.handle_end = frame_range.handle_end
        data.handles_in_files = frame_range.handles_in_files
        data.content_frame_start = frame_range.content_frame_start
        data.content_frame_end = frame_range.content_frame_end
        if frame_range.frame_rate is not None:
            data.fps = float(frame_range.frame_rate)

    if representation.contains_trait(Slate):
        data.slate_frames = representation.get_trait(Slate).frames

    if representation.contains_trait(ColorManaged):
        data.colorspace = representation.get_trait(ColorManaged).color_space

    return data


def get_version_attributes_with_traits(context: dict) -> dict[str, Any]:
    """Version attributes updated with values from representation traits.

    Loaders read frame range, handles, fps and colorspace from version
    attributes. Traits describe the loaded representation itself, so
    their values are used when available.

    Args:
        context (dict): Load context.

    Returns:
        dict[str, Any]: Copy of version attributes.

    """
    attributes = dict(context["version"]["attrib"])
    data = get_load_traits_data(context["representation"])
    if data is None:
        return attributes

    if data.content_frame_start is not None:
        attributes["handleStart"] = data.handle_start
        attributes["handleEnd"] = data.handle_end
        attributes["frameStart"] = data.content_frame_start
        attributes["frameEnd"] = data.content_frame_end

    if data.fps:
        attributes["fps"] = data.fps
    if data.colorspace:
        attributes["colorSpace"] = data.colorspace
    return attributes


def get_sequence_path(
    project_name: str,
    repre_entity: dict,
    traits_data: LoadTraitsData,
    frame: Optional[int] = None,
) -> Optional[str]:
    """Path to a sequence representation with frame or frame pattern.

    The representation template is filled with the frame formatted by
    `Sequence.frame_padding`, so the path does not depend on the frame
    stored in representation context.

    Args:
        project_name (str): Project name.
        repre_entity (dict): Representation entity.
        traits_data (LoadTraitsData): Data from representation traits.
        frame (Optional[int]): Frame number, frame pattern with hashes
            (e.g. "####") is used if not passed.

    Returns:
        Optional[str]: Path or None if representation is not a sequence
            with known frame padding.

    """
    padding = traits_data.frame_padding
    if not traits_data.is_sequence or not padding:
        return None

    if frame is None:
        frame_value = "#" * padding
    else:
        frame_value = f"{frame:0{padding}d}"

    repre_entity = copy.deepcopy(repre_entity)
    repre_entity["context"]["frame"] = frame_value
    path = get_representation_path(project_name, repre_entity)
    return path.replace("\\", "/")
