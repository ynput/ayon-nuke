""" AYON custom script for setting up write nodes for non-publish """
import os
import nuke
import nukescripts
from ayon_core.pipeline import Anatomy, get_current_project_name
from ayon_nuke.api.lib import (
    set_node_knobs_from_settings,
    get_nuke_imageio_settings,
    get_current_project_settings,
)


knobs_setting = {
    "knobs": [
        {
            "type": "text",
            "name": "file_type",
            "value": "exr"
        },
        {
            "type": "text",
            "name": "datatype",
            "value": "16 bit half"
        },
        {
            "type": "text",
            "name": "compression",
            "value": "Zip (1 scanline)"
        },
        {
            "type": "bool",
            "name": "autocrop",
            "value": True
        },
        {
            "type": "color_gui",
            "name": "tile_color",
            "value": [
                186,
                35,
                35,
                255
            ]
        },
        {
            "type": "text",
            "name": "channels",
            "value": "rgb"
        },
        {
            "type": "bool",
            "name": "create_directories",
            "value": True
        }
    ]
}


class WriteNodeKnobSettingPanel(nukescripts.PythonPanel):
    """ Write Node's Knobs Settings Panel """
    def __init__(self):
        nukescripts.PythonPanel.__init__(self, "Set Knobs Value(Write Node)")

        preset_names, _ = self.get_node_knobs_setting()
        # create knobs

        self.selected_preset_name = nuke.Enumeration_Knob(
            'preset_selector', 'presets', preset_names)
        # add knobs to panel
        self.addKnob(self.selected_preset_name)

    def process(self):
        """ Process the panel values. """
        write_selected_nodes = [
            selected_nodes for selected_nodes in nuke.selectedNodes()
            if selected_nodes.Class() == "Write"]

        selected_preset = self.selected_preset_name.value()
        ext = None
        knobs = knobs_setting["knobs"]
        preset_name, node_knobs_presets = (
            self.get_node_knobs_setting(selected_preset)
        )

        if selected_preset and preset_name:
            if not node_knobs_presets:
                nuke.message(
                    "No knobs value found in subset group.."
                    "\nDefault setting will be used..")
            else:
                knobs = node_knobs_presets

        knob_names = {knob["name"]: knob for knob in knobs}

        if "ext" in knob_names:
            ext = knob_names["ext"]["value"]
        elif "file_type" in knob_names:
            ext = knob_names["ext"]["value"]
        else:
            nuke.message(
                "ERROR: No 'file_type' nor 'ext' found in the product's knobs."
                "\nPlease add one to complete setting up the node")
            return

        anatomy = Anatomy(get_current_project_name())

        project_settings = get_current_project_settings()
        write_settings = project_settings["nuke"]["create"]["CreateWriteRender"]
        temp_rendering_path_template = write_settings["temp_rendering_path_template"]

        frame_padding = anatomy.templates_obj.frame_padding
        for write_node in write_selected_nodes:
            # data for mapping the path
            # TODO add more fill data
            product_name = write_node["name"].value()
            data = {
                "work": os.getenv("AYON_WORKDIR"),
                "product": {
                    "name": product_name,
                },
                "frame": "#" * frame_padding,
                "ext": ext
            }
            file_path = temp_rendering_path_template.format(**data)
            file_path = file_path.replace("\\", "/")
            write_node["file"].setValue(file_path)
            set_node_knobs_from_settings(write_node, knobs)

    def get_node_knobs_setting(self, selected_preset=None):
        preset_names = []
        knobs_nodes = []

        settings = [
            node_settings for node_settings
            in get_nuke_imageio_settings()["nodes"]["override_nodes"]
            if (
                    node_settings["nuke_node_class"] == "Write" or
                    node_settings["custom_class"] == "Write"
               )
            and node_settings.get("product_names", [])
        ]
        if not settings:
            return [], []

        for i, _ in enumerate(settings):
            if selected_preset in settings[i]["product_names"]:
                knobs_nodes = settings[i]["knobs"]

        for setting in settings:
            product_names = setting.get("product_names", [])
            preset_names.extend(iter(product_names))
        return preset_names, knobs_nodes


def main():
    p_ = WriteNodeKnobSettingPanel()
    if p_.showModalDialog():
        print(p_.process())
