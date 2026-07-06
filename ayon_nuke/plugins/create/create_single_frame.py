import os
import re
from ayon_nuke.api import NukeCreator
from ayon_nuke.api.plugin import CreatorError


class CreateSingleFrame(NukeCreator):
    """Create single frame render."""

    identifier = "create_single_frame"
    label = "Create Single Frame"
    description = "Creates a single frame render with optional frame token in variant."

    # Default settings
    default_variant = "{frame}"

    def get_pre_create_attr_defs(self):
        from ayon_core.lib import EnumDef
        return [
            EnumDef(
                "product_type",
                items=[
                    "single_frame",
                    "render"
                ],
                default="single_frame",
                label="Product type"
            )
        ]

    def create(self, product_name, data, pre_create_data):
        # Resolve frame token in variant
        variant = data.get("variant", "")
        if "{frame}" in variant:
            frame = data.get("frame", 1001)  # default fallback
            variant = variant.replace("{frame}", str(frame))
            data["variant"] = variant

        # Call parent
        super(CreateSingleFrame, self).create(product_name, data, pre_create_data)

    def get_publish_instance_collection_shared_data(self):
        return {
            "product_type": "single_frame"
        }

    def set_thumbnail(self, instance, thumbnail_path):
        # Implement thumbnail setting if needed
        pass
