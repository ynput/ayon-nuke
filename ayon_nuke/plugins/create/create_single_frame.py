import pyblish.api
from ayon_core.pipeline import Creator, CreatedInstance
from ayon_nuke import api as nuke_api

class CreateSingleFrame(Creator):
    identifier = "io.ayon.creators.nuke.singleframe"
    label = "Single Frame (Still)"
    product_type = "render"
    description = "Creates a single frame render"
    icon = "camera"
    enabled = True

    # Default attributes
    default_variants = ["Main", "Still"]

    # Token for frame number
    tokens = ["frame"]

    def create(self, product_name, instance_data, pre_create_data):
        # Ensure variant uses frame token if present
        variant = instance_data.get("variant", "")
        if "{frame}" in variant:
            # The frame will be resolved at publish time
            pass
        # Call parent create
        return super().create(product_name, instance_data, pre_create_data)

    def collect_instances(self):
        # Standard collection
        return super().collect_instances()

    def update_instances(self, update_list):
        # Standard update
        return super().update_instances(update_list)

    def remove_instances(self, instances):
        # Standard remove
        return super().remove_instances(instances)
