import nuke
from ayon_core.pipeline.create import Creator, CreatedInstance
from ayon_nuke.api import NukeCreator


class RenderStill(NukeCreator):
    """Render still image creator with {frame} token support."""
    identifier = "render_still"
    label = "Render still image"
    product_type = "render.still"
    description = "Creates a still frame render"

    default_variant = "Still"
    default_variants = [
        "main",
        "{frame}",
    ]

    def get_dynamic_data(
        self, variant, instance_data, pre_create_data
    ):
        dynamic_data = super().get_dynamic_data(
            variant, instance_data, pre_create_data
        )
        # Add frame token data from Nuke's current frame
        frame = nuke.frame()
        dynamic_data["frame"] = frame
        return dynamic_data

    def create_new_instance(
        self, instance_data: dict, pre_create_data: dict
    ) -> CreatedInstance:
        # After creation, store the current frame in instance data
        instance = super().create_new_instance(
            instance_data, pre_create_data
        )
        frame = nuke.frame()
        instance["frame"] = frame
        return instance

    def get_instance_variant(self, instance: CreatedInstance) -> str:
        # Resolve variant with frame token if present
        variant = instance["variant"]
        frame = instance.get("frame")
        if frame is not None:
            variant = variant.replace("{frame}", str(frame))
        return variant
