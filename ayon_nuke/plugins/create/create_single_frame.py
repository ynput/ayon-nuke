import os
import re

from ayon_nuke.api import plugin
from ayon_core.pipeline import CreatorError


class CreateSingleFrame(plugin.AutoCreator):
    """Creator for single frame renders."""

    identifier = "io.ayon.creators.nuke.singleframe"
    label = "Single Frame"
    product_type = "render"

    default_variant_expression = "{family}_{frame}"  # Updated to include frame

    def create(self, product_name, data, pre_create_data):
        # Ensure variant template uses {frame} token
        variant_template = data.get("variant", self.default_variant_expression)
        # Resolve frame token from context if present
        frame = self._get_frame_number(data)
        if frame is not None:
            variant_template = variant_template.replace("{frame}", str(frame))
        else:
            # Fallback if no frame: replace with empty or default
            variant_template = variant_template.replace("{frame}", "")
        # Update variant in data
        data["variant"] = variant_template
        super().create(product_name, data, pre_create_data)

    def _get_frame_number(self, data):
        """Extract frame number from context or data."""
        # Try to get from data
        frame = data.get("frame")
        if frame is not None:
            return frame
        # Try from current context (e.g., Nuke node's frame range)
        try:
            import nuke
            frame = nuke.frame()
            return frame
        except:
            return None
