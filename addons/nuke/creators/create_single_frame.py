import re
from ayon_core.pipeline.create import Creator
from ayon_nuke.api import NukeCreator


class CreateSingleFrame(NukeCreator):
    """Create single frame render instance."""

    def create(self, product_name, instance_data, source_script=None):
        # Allow {frame} token in variant
        variant = instance_data.get("variant", "")
        # Replace {frame} with actual frame number if present
        frame = instance_data.get("frameStart") or instance_data.get("frame")
        if frame is not None:
            variant = variant.replace("{frame}", str(int(frame)))
            # Also support {frame:04d} style padding? For now simple replace.
            # Could extend with regex for formatting.
        instance_data["variant"] = variant
        return super().create(product_name, instance_data, source_script)

    def _create_product_name(self, instance_data):
        """Override to process {frame} token in variant."""
        variant = instance_data.get("variant", "")
        frame = instance_data.get("frameStart") or instance_data.get("frame")
        if frame is not None:
            # Replace all occurrences of {frame} with the frame number
            variant = re.sub(r"\{frame\}", str(int(frame)), variant)
            # Support optional padding: {frame:04d} -> zero-padded 4 digits
            variant = re.sub(
                r"\{frame:(\d+)d\}",
                lambda m: str(int(frame)).zfill(int(m.group(1))),
                variant
            )
            instance_data["variant"] = variant
        return super()._create_product_name(instance_data)

    def get_instance_attributes(self):
        attributes = super().get_instance_attributes()
        # Ensure frame attribute is accessible
        attributes["frame"] = {
            "type": "integer",
            "label": "Frame",
            "default": 1001,
            "tooltip": "Frame number for single frame render"
        }
        return attributes
