"""Silhouette shapes extractor for Nuke."""
import os

import nuke
import pyblish.api

from ayon_core.pipeline import publish, OptionalPyblishPluginMixin
from ayon_core.lib import BoolDef
from ayon_nuke.api.lib import (
    maintained_selection,
    select_nodes
)

from ayon_nuke.vendor.NukeFXExporter import silhouetteFxsExporter


class ExtractSilhouetteShapes(publish.Extractor,
                              OptionalPyblishPluginMixin):
    """Silhouette shapes extractor"""
    label = 'Extract Silhouette Shapes'
    order = pyblish.api.ExtractorOrder
    families = ["matteshapes"]
    hosts = ["nuke"]

    settings_category = "nuke"

    def process(self, instance):
        first_frame = int(nuke.root()["first_frame"].getValue())
        last_frame = int(nuke.root()["last_frame"].getValue())

        self.log.debug(f"instance.data: `{instance.data}`")

        shape_node = instance.data["transientData"]["node"]

        product_name = instance.data["productName"]
        staging_dir = self.staging_dir(instance)

        # create file name and path
        filename = f"{product_name}.fxs"
        attr_values = self.get_attr_values_from_data(instance.data)
        filepath = os.path.join(staging_dir, filename)

        with maintained_selection():
            # select shapes node
            select_nodes([shape_node])
            silhouetteFxsExporter(
                filepath,
                first_frame,
                last_frame,
                bakeshapes=attr_values.get("bake_shapes", False)
            )

        # create representation data
        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': "fxs",
            'ext': "fxs",
            'files': filename,
            "stagingDir": staging_dir,
            "frameStart": first_frame,
            "frameEnd": last_frame
        }
        instance.data["representations"].append(representation)

    @classmethod
    def get_attribute_defs(cls):
        return [
            BoolDef(
                "bake_shapes",
                label="Bake Shapes",
                default=False,
            )
        ]
