import nuke
from ayon_nuke.api import plugin
from ayon_core.pipeline import CreatedInstance


class SingleFrameCreator(plugin.NukeCreator):
    """Creator for single frame renders with {frame} token support."""

    identifier = "io.ayon.creators.nuke.singleframe"
    label = "Single Frame"
    product_type = "render"
    icon = "camera"

    def get_instance_attributes(self, instance: CreatedInstance) -> dict:
        attributes = super().get_instance_attributes(instance)
        attributes["frame_token"] = "{frame}"
        return attributes

    def create(self, product_name: str, instance_data: dict, source: str = None):
        # Get variant from instance data
        variant = instance_data.get("variant", "")
        # Replace {frame} with the current frame number
        if "{frame}" in variant:
            current_frame = nuke.frame()
            variant = variant.replace("{frame}", str(int(current_frame)))
        instance_data["variant"] = variant
        super().create(product_name, instance_data, source)

    def collect_instance_attributes(self, instance: CreatedInstance):
        # Ensure variant uses the token if present
        super().collect_instance_attributes(instance)

    def update_instance(self, instance: CreatedInstance):
        # Refresh frame token during update
        super().update_instance(instance)
        variant = instance.data.get("variant", "")
        if "{frame}" in variant:
            current_frame = nuke.frame()
            new_variant = variant.replace("{frame}", str(int(current_frame)))
            instance.data["variant"] = new_variant
