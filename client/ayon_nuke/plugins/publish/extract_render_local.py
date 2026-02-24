"""
Removed Features:
- handle "frames to fix" logic
    imho this should be handled in a separate step, which would pass on a 
    "frames_to_render" list[int] that can then be used here.

- _copy_last_published function
    also: own step / combined with "frames to fix" logic

- adding the representation data to the instance data
    Should be done during collection (?)

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

    Allows to use last published frames and overwrite only specific ones
    (set in instance.data.get("frames_to_fix"))
    """

    order = pyblish.api.ExtractorOrder
    label = "Render Local"
    hosts = ["nuke"]
    families = ["render.local", "prerender.local", "image.local"]

    settings_category = "nuke"

    if typing.TYPE_CHECKING:
        log: logging.Logger

    def process(self, instance) -> None:
        node: nuke.Node = instance.data["transientData"]["node"]

        # Note: this step used to be used handle the "frames to fix"-logic.
        # That should be moved to its own step and pass on a "frames_to_render" list.
        # for now... we just render the entire sequence here
        first_frame = instance.data["frameStartHandle"]
        last_frame = instance.data["frameEndHandle"]
        frames_to_render = [(first_frame, last_frame)]

        for render_first_frame, render_last_frame in frames_to_render:
            self.log.info("Starting render")
            self.log.info("Start frame: {}".format(render_first_frame))
            self.log.info("End frame: {}".format(render_last_frame))
            # Render frames
            try:
                nuke.execute(
                    node,
                    int(render_first_frame),
                    int(render_last_frame)
                )
            except RuntimeError as exc:
                raise publish.PublishError(
                    title="Render Failed",
                    message=f"Failed to render {node.fullName()}",
                    description="Check Nuke console for more information.",
                    detail=str(exc),
                ) from exc

        # convert ".local" families back to their original versions
        families = instance.data["families"]
        for family in families:

            if family.endswith(".local"):
                families.remove(family)
                family = family.removesuffix(".local")
                instance.data["family"] =  family
                instance.data["productType"] = family  # not sure about this
        instance.data["families"] = families
