import nuke

from ayon_core.pipeline import CreatedInstance
from ayon_core.pipeline.create import (
    Creator,
    CreatedInstance,
    CreatorError,
    HiddenCreator,
)
from ayon_core.lib import BoolDef, IntDef, EnumDef, TextDef


class CreateStill(Creator):
    """Create a still frame export."""

    identifier = "create_still"
    label = "Still Frame"
    product_type = "render"
    icon = "camera"
    description = "Export current frame as a still image"

    # Default variant template that now supports {frame}
    default_variant = "still_{frame}"

    def get_pre_create_attr_defs(self):
        return [
            IntDef(
                "frame",
                default=int(nuke.frame()),
                label="Frame",
                tooltip="Frame number to render for still image.",
                decimals=0,
                minimum=0,
                maximum=1000000,
            )
        ]

    def create(self, product_name, data, pre_create_data):
        # Ensure frame is set
        frame = pre_create_data.get("frame")
        if frame is None:
            raise CreatorError("Frame is required for still creation.")

        # Prepare instance data
        instance_data = {
            "productName": product_name,
            "productType": self.product_type,
            "frameStart": frame,
            "frameEnd": frame,
            "step": 1,
        }

        # Collect current node selection or write node
        # Implementation details: create a write node set to frame range
        write_node = nuke.createNode("Write")
        write_node["file"].set(self._get_output_path(product_name, frame))
        write_node["first"].set(frame)
        write_node["last"].set(frame)
        write_node["use_limit"].set(True)

        # Add metadata for AYON
        tab = nuke.Tab_Knob("ayon")
        write_node.addKnob(tab)
        write_node["label"].set(f"AYON: {product_name}")

        # Return instance
        return CreatedInstance(
            self.product_type,
            product_name,
            instance_data,
            self,
            node=write_node
        )

    def _get_output_path(self, product_name, frame):
        """Construct output path using variant template."""
        # Assuming the context provides the template with {frame} token
        from nuke.ayon.utils import get_variant_template_context
        context = get_variant_template_context(self, product_name, frame=frame)
        return context.format_variant(self.variant or self.default_variant)

    def get_instance_attr_defs(self):
        return [
            IntDef(
                "frame",
                default=self._get_current_frame(),
                label="Frame",
                tooltip="Frame number to render.",
                decimals=0,
                minimum=0,
                maximum=1000000,
            ),
            BoolDef(
                "use_limit",
                default=True,
                label="Use Frame Range",
                tooltip="Render only the specified frame.",
            ),
        ]

    def _get_current_frame(self):
        try:
            return int(nuke.frame())
        except:
            return 1001
