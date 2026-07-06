import nuke
from ayon_nuke.api.creator import NukeCreator

class SingleFrameCreator(NukeCreator):
    """Creates a single frame render with frame token support in variant."""

    identifier = "single_frame_creator"
    label = "Single Frame Creator"
    product_type = "render"
    default_variants = ["Still"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._frame = None

    def get_pre_create_attr_defs(self):
        """Override to add frame number input."""
        import pyblish.api
        from ayon_core.lib import (
            BoolDef,
            NumberDef,
            UILabelDef,
        )
        return super().get_pre_create_attr_defs() + [
            NumberDef(
                "frame",
                label="Frame Number",
                default=int(nuke.frame()),
                decimals=0,
                minimum=1,
                tooltip="Frame number to render for still image. "
                        "Will replace {frame} in variant template."
            )
        ]

    def create(self, product_name, instance_data, pre_create_data):
        # Store frame from pre_create_data if provided
        if "frame" in pre_create_data:
            self._frame = int(pre_create_data["frame"])
        else:
            self._frame = int(nuke.frame())
        super().create(product_name, instance_data, pre_create_data)

    def _get_variant(self, instance_data, pre_create_data):
        """Overridden to replace {frame} in variant with actual frame."""
        variant = super()._get_variant(instance_data, pre_create_data)
        if variant and "{frame}" in variant:
            frame_str = str(self._frame).zfill(4)
            variant = variant.replace("{frame}", frame_str)
        return variant

    def collect_instances(self):
        super().collect_instances()
        # No additional collection needed
        pass

    def update_instances(self, instance_list):
        super().update_instances(instance_list)
        # Update frame token if variant changed
        for instance in instance_list:
            if instance.get("creator_identifier") == self.identifier:
                variant = instance.get("variant")
                if variant and "{frame}" in variant:
                    # Replace with stored or current frame
                    frame = instance.get("frame", int(nuke.frame()))
                    instance["variant"] = variant.replace(
                        "{frame}", str(frame).zfill(4)
                    )
```