from ayon_nuke.api import NukeCreator
import nuke

class CreateRenderProduct(NukeCreator):
    """Creates Render Product instances."""

    frame_range_handles = True

    def _create_instance_attributes(self, instance_data, subset_name):
        # Inherit frame range from script root if not explicitly set
        root = nuke.root()
        attr = instance_data.setdefault("frameStart", root["first_frame"].value())
        attr = instance_data.setdefault("frameEnd", root["last_frame"].value())
        return super()._create_instance_attributes(instance_data, subset_name)
