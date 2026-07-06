import nuke
from ayon_nuke.api import NukeCreator
from ayon_core.pipeline import CreatorError


class CreateSingleFrame(NukeCreator):
    """Create single frame render instance with {frame} token support."""

    identifier = "io.ayon.creators.nuke.singleframe"
    label = "Single Frame"
    description = "Creates a still frame render"
    product_type = "render"
    icon = "camera"
    default_variant = "Still{frame}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._frame_token = "{frame}"

    @classmethod
    def get_available_tokens(cls):
        """Return list of tokens available for variant template."""
        tokens = super().get_available_tokens()
        tokens.append("{frame}")
        return tokens

    def create(self, product_name=None, instance_data=None, pre_create_data=None):
        # Process variant template to replace {frame} with actual frame
        variant = instance_data.get("variant", "")
        frame_number = instance_data.get("frame", nuke.frame())
        if self._frame_token in variant:
            # Ensure frame is an integer or string
            variant = variant.replace(self._frame_token, str(frame_number))
            instance_data["variant"] = variant
        return super().create(product_name, instance_data, pre_create_data)

    def get_pre_create_widget(self):
        widget = super().get_pre_create_widget()
        # Add frame number input if not present
        from ayon_core.tools.creator.utils import TextInputWidget
        frame_input = TextInputWidget(
            "Frame Number",
            default=str(nuke.frame()),
            placeholder="Enter frame number or use {frame}"
        )
        widget.add_input(frame_input, "frame")
        return widget

    def get_instance_data(self, pre_create_data):
        data = super().get_instance_data(pre_create_data)
        # Store frame number from UI
        if pre_create_data:
            frame_str = pre_create_data.get("frame", "")
            if frame_str.isdigit():
                data["frame"] = int(frame_str)
            else:
                data["frame"] = nuke.frame()
        return data

    def collect_instances(self):
        super().collect_instances()
        # Ensure existing instances without frame variable still work
        for instance in self.instances:
            variant = instance.get("variant", "")
            if self._frame_token in variant:
                # Replace with stored frame if available
                frame = instance.get("frame", nuke.frame())
                variant = variant.replace(self._frame_token, str(frame))
                instance["variant"] = variant
