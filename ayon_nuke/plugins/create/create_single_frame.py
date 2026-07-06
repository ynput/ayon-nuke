from ayon_nuke.api import NukeCreator
from ayon_core.lib import TextDef
import nuke


class SingleFrameCreator(NukeCreator):
    identifier = "io.ayon.creators.nuke.singleframe"
    product_type = "render"
    description = "Create a single frame render"
    default_variant = "{frame}"

    def get_precreate_attr_defs(self):
        return [
            TextDef("variant", default=self.default_variant,
                    label="Variant template",
                    placeholder="e.g., main or {frame}"),
        ]

    def create(self, product_name, instance_data, pre_create_data):
        # Determine the frame from current context
        frame = int(nuke.numvalue("frame"))
        instance_data["frame"] = frame

        # Process variant template
        variant_template = pre_create_data.get("variant", self.default_variant)
        if variant_template:
            variant = variant_template.replace("{frame}", str(frame))
            instance_data["variant"] = variant
        else:
            variant = ""

        # Override product_name with variant if needed
        if product_name and variant:
            product_name = f"{product_name}_{variant}"
        super().create(product_name, instance_data, pre_create_data)
