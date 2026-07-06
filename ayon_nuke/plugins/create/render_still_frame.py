import nuke

from ayon_nuke.api import NukeCreator


class RenderStillFrameCreator(NukeCreator):
    """Creator for rendering a single still frame."""

    identifier = "render.still.frame"
    label = "Render Still Frame"
    product_type = "render.still.frame"
    description = "Creates a single still frame render"

    def create(self, product_name, instance_data, pre_create_data):
        # Add frame token to variant template context
        # Get the current frame from the instance or knob
        frame = nuke.frame()
        instance_data["frame"] = frame
        super().create(product_name, instance_data, pre_create_data)

    def get_instance_attribute_values(self, instance):
        data = super().get_instance_attribute_values(instance)
        # Include frame in the context for template resolution
        data["frame"] = instance["frame"]
        return data

    def get_variant_tokens(self, instance):
        tokens = super().get_variant_tokens(instance)
        tokens["frame"] = str(instance.get("frame", nuke.frame()))
        return tokens

    def get_variant_example(self):
        example = super().get_variant_example()
        return example + "_{frame}"
