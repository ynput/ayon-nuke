"""Helpers for publishing trait based representations in Nuke.

Render targets processed inside Nuke ("local" and "frames") always publish
trait representations. Farm targets create their representations on the
farm and keep using legacy dictionaries.

An instance uses either trait representations or legacy dictionaries,
never both - `Integrate` in ayon-core skips instances with trait
representations and `IntegrateTraits` integrates them.

Loaders work with traits of every representation, see `load_traits.py`.
"""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Optional

import nuke

from ayon_core.pipeline.colorspace import (
    set_colorspace_data_to_representation,
)
from ayon_core.pipeline.publish import (
    get_trait_representations as _get_trait_representations,
)
from ayon_core.pipeline.publish.review_utils import DEFAULT_IMAGE_EXTS
from ayon_core.pipeline.publish.trait_conversion import (
    color_managed_from_colorspace_data,
    sequence_traits_from_files,
)
from ayon_core.pipeline.traits import (
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


def get_trait_representations(instance) -> list:
    """Trait representations of instance.

    Returns:
        list[Representation]: Trait representations.

    """
    return list(_get_trait_representations(instance))


def add_slate_trait(representation: Representation, frames: int = 1) -> None:
    """Mark representation as having slate frames at the start."""
    if not representation.contains_trait(Slate):
        representation.add_trait(Slate(frames=frames))


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
