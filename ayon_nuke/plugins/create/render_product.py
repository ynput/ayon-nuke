import nuke
from ayon_core.pipeline import Creator, CreatedInstance
from ayon_nuke.api import NukeCreator

class CreateRenderProduct(NukeCreator):
    """Create render product with optional custom frame range."""

    def create(self, product_name, data, pre_create_data):
        # Ensure custom frame range inherits script root if not explicitly set
        if data.get("custom_frame_range"):
            frame_range_start = data.get("frame_range_start")
            frame_range_end = data.get("frame_range_end")
            if frame_range_start is None or frame_range_end is None:
                root = nuke.root()
                first = root["first_frame"].value()
                last = root["last_frame"].value()
                if frame_range_start is None:
                    data["frame_range_start"] = first
                if frame_range_end is None:
                    data["frame_range_end"] = last
        return super().create(product_name, data, pre_create_data)
