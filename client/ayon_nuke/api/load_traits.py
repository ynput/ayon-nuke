"""Trait based representation data for loaders.

Proof of concept of trait first loading. Loaders get a trait
`Representation` for every representation entity and read information
(files, frame range, handles, slate, colorspace) from its traits:

- representation published with traits is restored from the "traits"
  field of the entity and traits it is missing are completed from the
  legacy data,
- legacy representation (without traits) is converted to traits from
  the legacy data - representation files, data and version attributes.

Converted legacy representations must load exactly as before traits.
Conversion uses the same inputs loaders used for legacy representations
(version attributes, representation data and template) and
`LoadRepresentation.is_converted` lets loaders keep their legacy rules
(e.g. how slate frames extend the frame range) on top of the traits.

Nothing in this module is specific to Nuke - it is meant to be moved
to `ayon_core.pipeline.load` and shared by all host integrations.
"""
from __future__ import annotations

import copy
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from ayon_core.lib import Logger
from ayon_core.pipeline import Anatomy
from ayon_core.pipeline.load import (
    get_representation_file_paths,
    get_representation_path,
    get_representation_traits,
)
from ayon_core.pipeline.publish.review_utils import DEFAULT_IMAGE_EXTS
from ayon_core.pipeline.publish.trait_conversion import (
    color_managed_from_colorspace_data,
    sequence_traits_from_files,
)
from ayon_core.pipeline.traits import (
    ColorManaged,
    Deep,
    FileLocation,
    FileLocations,
    FrameRanged,
    Handles,
    Image,
    MimeType,
    Representation,
    RootlessLocation,
    Sequence,
    Slate,
    get_frame_range_data,
)

if TYPE_CHECKING:
    from ayon_core.pipeline.traits import FrameRangeData, TraitBase

log = Logger.get_logger(__name__)

FILE_TRAITS: tuple[type[TraitBase], ...] = (
    FileLocation, FileLocations, Sequence)
# Traits completed together from legacy data - a trait representation
#   gets the group only when it has none of the traits of the group, so
#   traits created from different sources are never mixed.
COMPLETION_TRAIT_GROUPS: tuple[tuple[type[TraitBase], ...], ...] = (
    FILE_TRAITS,
    (FrameRanged, Handles),
    (Slate,),
    (ColorManaged,),
    (MimeType,),
    (Image,),
)


# --- Representation for loading -----------------------------------------
def get_context_anatomy(context: dict[str, Any]) -> Anatomy:
    """Project anatomy from project entity of load context."""
    project_entity = context["project"]
    return Anatomy(project_entity["name"], project_entity=project_entity)


def restore_representation(
    repre_entity: dict[str, Any],
) -> Optional[Representation]:
    """Representation restored from traits stored on entity.

    Returns:
        Optional[Representation]: Representation or None if entity has
            no traits or they can't be read.

    """
    try:
        return get_representation_traits(repre_entity)
    except Exception:  # noqa: BLE001
        log.warning(
            "Failed to read traits of representation {representation_id},"
            " using traits converted from legacy data",
            exc_info=True,
            representation_id=repre_entity.get("id"),
            representation_name=repre_entity.get("name"),
        )
    return None


def get_load_representation(
    context: dict[str, Any],
    anatomy: Optional[Anatomy] = None,
) -> Representation:
    """Get trait representation of the loaded representation entity.

    Args:
        context (dict[str, Any]): Load context with "representation",
            "version" and "project" entities.
        anatomy (Optional[Anatomy]): Project anatomy used to resolve
            paths of legacy representation files. Created from the
            project entity in context if not passed.

    Returns:
        Representation: Representation with traits.

    """
    representation, _ = _get_load_representation(context, anatomy)
    return representation


def _get_load_representation(
    context: dict[str, Any],
    anatomy: Optional[Anatomy] = None,
) -> tuple[Representation, bool]:
    """Representation and whether it was converted from legacy data."""
    repre_entity = context["representation"]
    if anatomy is None:
        anatomy = get_context_anatomy(context)

    legacy_representation = convert_entity_to_representation(
        repre_entity, context.get("version"), anatomy
    )
    representation = restore_representation(repre_entity)
    if representation is None:
        return legacy_representation, True

    has_entity_files = any(
        legacy_representation.contains_trait(trait) for trait in FILE_TRAITS
    )
    if (
        has_entity_files
        and not representation.contains_trait(RootlessLocation)
    ):
        # Paths in file traits are absolute paths at the time of
        #   publishing - files from entity are resolved with current roots
        for trait in FILE_TRAITS:
            if representation.contains_trait(trait):
                representation.remove_trait(trait)

    complete_representation(representation, legacy_representation)
    return representation, False


def complete_representation(
    representation: Representation,
    source: Representation,
) -> list[type[TraitBase]]:
    """Add traits missing in representation from another representation.

    Traits are added by `COMPLETION_TRAIT_GROUPS` - group of traits is
    added only when the representation has none of its traits.

    Args:
        representation (Representation): Representation to complete.
        source (Representation): Representation with traits to add,
            e.g. converted from legacy data.

    Returns:
        list[type[TraitBase]]: Trait classes added to representation.

    """
    added = []
    for group in COMPLETION_TRAIT_GROUPS:
        if any(representation.contains_trait(trait) for trait in group):
            continue
        for trait in group:
            if source.contains_trait(trait):
                representation.add_trait(source.get_trait(trait))
                added.append(trait)
    return added


def convert_entity_to_representation(
    repre_entity: dict[str, Any],
    version_entity: Optional[dict[str, Any]],
    anatomy: Anatomy,
) -> Representation:
    """Convert legacy representation entity to trait representation.

    Traits are created from the same data loaders used for legacy
    representations:

    - files of the entity (roots filled with anatomy) become
      `FileLocation`/`FileLocations`, multiple files also `Sequence`
      with frame padding of the frame in representation context,
    - frame range and handles of version become `FrameRanged` (handles
      and slate are expected in the files) and `Handles`,
    - "slateFrames" in representation data becomes `Slate`,
    - colorspace of representation data ("colorspaceData", then
      "colorspace") or "colorSpace" version attribute becomes
      `ColorManaged`.

    Args:
        repre_entity (dict[str, Any]): Representation entity.
        version_entity (Optional[dict[str, Any]]): Version entity.
        anatomy (Anatomy): Project anatomy to fill roots in file paths.

    Returns:
        Representation: Representation with traits.

    """
    version_attributes = (version_entity or {}).get("attrib") or {}
    repre_data = repre_entity.get("data") or {}
    repre_context = repre_entity.get("context") or {}
    fps = version_attributes.get("fps")
    representation = Representation(
        name=repre_entity["name"],
        representation_id=repre_entity.get("id"),
    )

    paths = [
        Path(anatomy.fill_root(file_info["path"]))
        for file_info in repre_entity.get("files") or []
        if file_info.get("path")
    ]
    if len(paths) == 1:
        representation.add_trait(FileLocation(file_path=paths[0]))
    elif paths:
        representation.add_trait(FileLocations(file_paths=[
            FileLocation(file_path=path) for path in paths
        ]))
        sequence_traits = sequence_traits_from_files(paths, fps=fps)
        if sequence_traits is not None:
            sequence = sequence_traits[1]
            frame = repre_context.get("frame")
            if frame:
                # padding of the frame used in templates
                sequence.frame_padding = len(str(frame))
            representation.add_trait(sequence)

    slate_frames = repre_data.get("slateFrames") or 0
    if slate_frames:
        representation.add_trait(Slate(frames=slate_frames))

    frame_start = version_attributes.get("frameStart")
    frame_end = version_attributes.get("frameEnd")
    if frame_start is not None and frame_end is not None:
        handle_start = version_attributes.get("handleStart") or 0
        handle_end = version_attributes.get("handleEnd") or 0
        frame_ranged = FrameRanged(
            frame_start=frame_start - handle_start - slate_frames,
            frame_end=frame_end + handle_end,
        )
        if fps:
            frame_ranged.frame_rate = fps
        representation.add_trait(frame_ranged)
        representation.add_trait(Handles(
            inclusive=True,
            frame_start_handle=handle_start,
            frame_end_handle=handle_end,
        ))

    color_managed = _get_legacy_color_managed(repre_data, version_attributes)
    if color_managed is not None:
        representation.add_trait(color_managed)

    ext = repre_context.get("ext")
    if not ext and paths:
        ext = paths[0].suffix.lstrip(".")
    if ext:
        mime_type, _ = mimetypes.guess_type(f"file.{ext.lower()}")
        if mime_type:
            representation.add_trait(MimeType(mime_type=mime_type))
        if ext.lower() in DEFAULT_IMAGE_EXTS:
            representation.add_trait(Image())

    return representation


def _get_legacy_color_managed(
    repre_data: dict[str, Any],
    version_attributes: dict[str, Any],
) -> Optional[ColorManaged]:
    """Colorspace of legacy representation as `ColorManaged` trait.

    Same order as loaders used for legacy representations -
    "colorspaceData", "colorspace" of representation data and
    "colorSpace" version attribute.
    """
    color_managed = color_managed_from_colorspace_data(
        repre_data.get("colorspaceData")
    )
    if color_managed is not None:
        return color_managed

    colorspace = (
        repre_data.get("colorspace")
        or version_attributes.get("colorSpace")
    )
    if colorspace:
        return ColorManaged(color_space=colorspace)
    return None


# --- Values from traits -------------------------------------------------
def is_sequence(representation: Representation) -> bool:
    """Representation is a sequence of frames."""
    if representation.contains_trait(Sequence):
        return True
    return get_file_count(representation) > 1


def get_file_count(representation: Representation) -> int:
    """Number of files of representation."""
    if representation.contains_trait(FileLocations):
        return len(representation.get_trait(FileLocations).file_paths)
    if representation.contains_trait(FileLocation):
        return 1
    return 0


def get_extension(representation: Representation) -> Optional[str]:
    """Extension of representation files without dot (case kept)."""
    if representation.contains_trait(FileLocations):
        file_paths = representation.get_trait(FileLocations).file_paths
        if not file_paths:
            return None
        path = Path(file_paths[0].file_path)
    elif representation.contains_trait(FileLocation):
        path = Path(representation.get_trait(FileLocation).file_path)
    else:
        return None
    return path.suffix.lstrip(".") or None


def is_deep(representation: Representation) -> bool:
    """Representation contains deep image data."""
    return representation.contains_trait(Deep)


def get_slate_frames(representation: Representation) -> int:
    """Number of slate frames at the start of the representation."""
    if representation.contains_trait(Slate):
        return representation.get_trait(Slate).frames
    return 0


def get_colorspace(representation: Representation) -> Optional[str]:
    """Colorspace of representation files."""
    if representation.contains_trait(ColorManaged):
        return representation.get_trait(ColorManaged).color_space
    return None


def get_frame_range(
    representation: Representation,
) -> Optional[FrameRangeData]:
    """Frame range of representation files and content.

    Returns:
        Optional[FrameRangeData]: Frame range or None if representation
            does not have `FrameRanged` trait.

    """
    return get_frame_range_data(representation)


def get_version_attributes(
    representation: Representation,
    version_entity: dict[str, Any],
) -> dict[str, Any]:
    """Version attributes with values of the representation traits.

    Frame range (without slate and handles), handles, fps and colorspace
    are taken from traits - they describe the loaded representation.
    Other attributes (e.g. "source") are kept.

    Args:
        representation (Representation): Loaded representation.
        version_entity (dict[str, Any]): Version entity.

    Returns:
        dict[str, Any]: Copy of version attributes.

    """
    attributes = dict(version_entity.get("attrib") or {})
    frame_range = get_frame_range(representation)
    if frame_range is not None:
        attributes["frameStart"] = frame_range.content_frame_start
        attributes["frameEnd"] = frame_range.content_frame_end
        attributes["handleStart"] = frame_range.handle_start
        attributes["handleEnd"] = frame_range.handle_end
        if frame_range.frame_rate is not None:
            attributes["fps"] = float(frame_range.frame_rate)

    colorspace = get_colorspace(representation)
    if colorspace:
        attributes["colorSpace"] = colorspace
    return attributes


def get_file_path(
    representation: Representation,
    anatomy: Anatomy,
    frame: Optional[int] = None,
    frame_token: str = "#",
) -> Optional[str]:
    """Path to representation file, frame of a sequence or its pattern.

    Path of single file representation is returned as is. For sequence
    the frame number in file name is replaced with the frame (padded)
    or with frame pattern - `frame_token` repeated by frame padding
    (e.g. "####") when frame is not passed.

    Args:
        representation (Representation): Representation with traits.
        anatomy (Anatomy): Project anatomy to fill roots.
        frame (Optional[int]): Frame of a sequence.
        frame_token (str): Character used for frame pattern.

    Returns:
        Optional[str]: Path or None if representation has no files or
            frame can't be found in file name of sequence.

    """
    file_paths = get_representation_file_paths(representation, anatomy)
    if not file_paths:
        return None

    first_path = Path(file_paths[0])
    if not is_sequence(representation):
        return first_path.as_posix()

    padding = None
    if representation.contains_trait(Sequence):
        sequence = representation.get_trait(Sequence)
        pattern = sequence.get_frame_pattern()
        padding = sequence.frame_padding
    else:
        pattern = Sequence(frame_padding=0).get_frame_pattern()

    match = pattern.search(first_path.name)
    if match is None:
        return None

    padding = padding or len(match.group("index"))
    if frame is None:
        frame_value = frame_token * padding
    else:
        frame_value = f"{int(frame):0{padding}d}"
    index_start, index_end = match.span("index")
    filename = (
        first_path.name[:index_start]
        + frame_value
        + first_path.name[index_end:]
    )
    return (first_path.parent / filename).as_posix()


def get_first_file_path(
    representation: Representation,
    anatomy: Anatomy,
) -> Optional[str]:
    """Path to the first file of representation."""
    file_paths = get_representation_file_paths(representation, anatomy)
    if not file_paths:
        return None
    return Path(file_paths[0]).as_posix()


# --- Legacy paths -------------------------------------------------------
def get_legacy_file_path(
    project_name: str,
    repre_entity: dict[str, Any],
    anatomy: Optional[Anatomy] = None,
    frame: Optional[int] = None,
    frame_token: Optional[str] = None,
) -> Optional[str]:
    """Path of legacy representation filled from its template.

    Same resolution as loaders used before traits:

    - without arguments it is the template path of the representation,
    - with `frame_token` the frame in context of a sequence is replaced
      with the token repeated by length of the frame (and in
      "originalBasename" when template uses it),
    - with `frame` the frame of the representation context is replaced
      in the path with the frame padded to the same length.

    Args:
        project_name (str): Project name.
        repre_entity (dict[str, Any]): Representation entity.
        anatomy (Optional[Anatomy]): Project anatomy.
        frame (Optional[int]): Frame to replace in the path.
        frame_token (Optional[str]): Token for frame pattern of sequence.

    Returns:
        Optional[str]: Path with forward slashes.

    """
    if frame_token and len(repre_entity.get("files") or []) > 1:
        repre_entity = _get_entity_with_frame_pattern(
            repre_entity, frame_token)

    path = get_representation_path(
        project_name, repre_entity, anatomy=anatomy
    )
    if not path:
        return None
    path = str(path).replace("\\", "/")

    context_frame = (repre_entity.get("context") or {}).get("frame")
    if frame is not None and context_frame:
        padding = len(context_frame)
        path = path.replace(
            context_frame, format(frame, "0{}".format(padding))
        )
    return path


def _get_entity_with_frame_pattern(
    repre_entity: dict[str, Any],
    frame_token: str,
) -> dict[str, Any]:
    """Entity copy with frame in context replaced with frame pattern."""
    new_repre_entity = copy.deepcopy(repre_entity)
    context = new_repre_entity["context"]

    frame = context["frame"]
    hashed_frame = frame_token * len(str(frame))

    if "{originalBasename}" in new_repre_entity["attrib"]["template"]:
        context["originalBasename"] = context["originalBasename"].replace(
            frame, hashed_frame
        )
    context["frame"] = hashed_frame
    return new_repre_entity


# --- Loader convenience -------------------------------------------------
@dataclass
class LoadRepresentation:
    """Trait representation of loaded context with resolved values.

    Representation and anatomy are created once and passed around.

    Attributes:
        representation (Representation): Representation with traits.
        anatomy (Anatomy): Project anatomy.
        context (dict[str, Any]): Load context.
        is_converted (bool): Representation has no traits, it was
            converted from legacy data. Loaders keep legacy rules for
            it, so it loads the same as before traits.

    """
    representation: Representation
    anatomy: Anatomy
    context: dict[str, Any] = field(repr=False)
    is_converted: bool = False

    @classmethod
    def from_context(
        cls,
        context: dict[str, Any],
        anatomy: Optional[Anatomy] = None,
    ) -> LoadRepresentation:
        """Create from load context."""
        if anatomy is None:
            anatomy = get_context_anatomy(context)
        representation, is_converted = _get_load_representation(
            context, anatomy
        )
        return cls(
            representation=representation,
            anatomy=anatomy,
            context=context,
            is_converted=is_converted,
        )

    @property
    def project_name(self) -> str:
        return self.context["project"]["name"]

    @property
    def repre_entity(self) -> dict[str, Any]:
        return self.context["representation"]

    @property
    def version_entity(self) -> dict[str, Any]:
        return self.context["version"]

    @property
    def is_sequence(self) -> bool:
        return is_sequence(self.representation)

    @property
    def file_count(self) -> int:
        return get_file_count(self.representation)

    @property
    def extension(self) -> Optional[str]:
        return get_extension(self.representation)

    @property
    def is_deep(self) -> bool:
        return is_deep(self.representation)

    @property
    def slate_frames(self) -> int:
        return get_slate_frames(self.representation)

    @property
    def colorspace(self) -> Optional[str]:
        return get_colorspace(self.representation)

    @property
    def frame_range(self) -> Optional[FrameRangeData]:
        return get_frame_range(self.representation)

    @property
    def version_attributes(self) -> dict[str, Any]:
        """Version attributes, with values of traits if published with them.

        Converted legacy representation gets unchanged copy of version
        attributes.
        """
        if self.is_converted:
            return dict(self.version_entity["attrib"])
        return get_version_attributes(
            self.representation, self.version_entity
        )

    def get_file_path(
        self,
        frame: Optional[int] = None,
        frame_token: str = "#",
    ) -> Optional[str]:
        """Path to file, frame of a sequence or frame pattern.

        Converted legacy representation resolves the path from its
        template, same as before traits.
        """
        if self.is_converted:
            return get_legacy_file_path(
                self.project_name,
                self.repre_entity,
                self.anatomy,
                frame=frame,
                frame_token=None if frame is not None else frame_token,
            )
        return get_file_path(
            self.representation, self.anatomy, frame, frame_token
        )

    def get_first_file_path(self) -> Optional[str]:
        """Path to the first file (template path of legacy)."""
        if self.is_converted:
            return get_legacy_file_path(
                self.project_name, self.repre_entity, self.anatomy
            )
        return get_first_file_path(self.representation, self.anatomy)
