"""

## notes:

Removed Features:
- handle "frames to fix" logic
    imho this should be handled in a separate step, which would pass on a
    "frames_to_render" list[int] that can then be used here.

- _copy_last_published function
    also: own step / combined with "frames to fix" logic

- adding the representation data to the instance data
    Should be done during collection (?)

- this step was setting the "productType" to the "family" after removing
  the ".local" suffix.
  I dont think this should be done here in this step.
  The purpose of this step is to render frames, It should not change the productType.


"""

import logging
import typing

import pyblish.api
import nuke
from ayon_core.pipeline import publish


class NukeRenderLocal(
    publish.Extractor,
    publish.ColormanagedPyblishPluginMixin,
):
    """Render the current Nuke composition locally.

    Extract the result of savers by starting a comp render
    This will run the local render of Nuke.

    Uses the following instance data:
    - "frames_to_render": list[int] optional
    - "frameStartHandle" or "frameStart"
    - "frameEndHandle" or "frameEnd"
    - "writeNode" or "node": the node to render

    """

    order = pyblish.api.ExtractorOrder
    label = "Render Local"
    hosts = ["nuke"]
    families = ["render.local", "prerender.local", "image.local"]

    settings_category = "nuke"

    if typing.TYPE_CHECKING:
        log: logging.Logger

    def _get_framerange_from_instance(self, instance) -> nuke.FrameRanges:
        """Get frame range from instance data.

        Args:
            instance (pyblish.api.Instance): pyblish instance

        Returns:
            list[nuke.FrameRange] | nuke.FrameRanges: frame range
        """
        # Check for a custom list of frames
        # this could be the result of an expression ("1001-1050x5")
        # and/or as a result of a previous step (eg.: "frames to fix")
        # Note:
        # `nuke.FrameRanges` supports list[int] as well as some expressions
        # (eg.: "1001-1050x5") see: https://learn.foundry.com/nuke/content/getting_started/managing_scripts/defining_frame_ranges.html
        # We should however change this to an ayon standardized format,
        # thats familiar across DCC's (or maybe support both: nuke and ayon)
        if "frames_to_render" in instance.data:
            frames_to_render = instance.data["frames_to_render"]
            return nuke.FrameRanges(frames_to_render)

        # If no custom list of frames is found, use the frame range from the instance data
        start = instance.data.get("frameStartHandle") or instance.data.get("frameStart")
        end = instance.data.get("frameEndHandle") or instance.data.get("frameEnd")
        step = 1

        frame_ranges = nuke.FrameRanges()
        frame_ranges.add(nuke.FrameRange(start, end, step))
        return frame_ranges

    def process(self, instance) -> None:

        node: nuke.Node = instance.data["transientData"].get("writeNode")
        node = node or instance.data["transientData"].get("node")

        frame_ranges = self._get_framerange_from_instance(instance)

        try:
            nuke.execute(node, frame_ranges)
        except RuntimeError as exc:
            raise publish.PublishError(
                title="Render Failed",
                message=f"Failed to render {node.fullName()}",
                description="Check Nuke console for more information.",
                detail=str(exc),
            ) from exc

        # convert ".local" families back to their original versions
        families = instance.data["families"]
        families = [family.removesuffix(".local") for family in families]
        # there might be duplicates after removing the suffix
        families = list(set(families))
        instance.data["families"] = families
