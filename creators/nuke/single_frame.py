import nuke
from ayon_core.pipeline import Creator
from ayon_core.pipeline.create import CreatedInstance

class SingleFrameCreator(Creator):
    """Creator for single frame renders with variant token support."""
    identifier = "io.ayon.creators.nuke.singleframe"
    label = "Single Frame"
    product_type = "render"
    icon = "camera"
    default_variant = "Still"

    def create(self, product_name, instance_data, pre_create_data):
        # Get frame number from pre_create_data or current frame
        frame = pre_create_data.get("frame", None)
        if frame is None:
            frame = int(nuke.frame())
        instance_data["frame"] = frame

        # Process variant token {frame}
        variant = instance_data.get("variant", "")
        if variant and "{frame}" in variant:
            variant = variant.replace("{frame}", str(frame))
            instance_data["variant"] = variant

        # Create instance
        instance = CreatedInstance(
            self.product_type, product_name, instance_data, self
        )
        instance["creator_attributes"]["frame"] = frame
        return instance

    def get_icon(self):
        return self.icon
