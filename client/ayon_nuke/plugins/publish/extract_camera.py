import os
import math

import nuke

import pyblish.api

from ayon_core.pipeline import publish
from ayon_nuke.api.lib import maintained_selection
from ayon_nuke.api.plugin import get_publish_config


class ExtractCamera(publish.Extractor):
    """ 3D camera extractor
    """
    label = 'Extract Camera'
    order = pyblish.api.ExtractorOrder
    families = ["camera"]
    hosts = ["nuke"]

    settings_category = "nuke"

    def _get_camera_export_presets(self, instance):
        """
        Args:
            instance (dict): The current instance being published.

        Returns:
            list: The camera export presets to use.
        """
        write_geo_knobs = [
            ("writeGeometries", False),
            ("writePointClouds", False),
            ("writeAxes", False)
        ]

        publish_settings = get_publish_config()
        extract_camera_settings = publish_settings.get("ExtractCameraFormat", {})
        export_camera_settings = extract_camera_settings.get("export_camera_format", "abc")

        if export_camera_settings == "abc":
            write_geo_knobs.insert(0, ("file_type", "abc"))
            write_geo_knobs.append((("storageFormat", "Ogawa")))

        elif export_camera_settings == "fbx":
            write_geo_knobs.insert(0, ("file_type", "fbx"))            
            write_geo_knobs.append(("writeLights", False))            

        else:
            raise ValueError(
                f"Invalid Camera export format: {export_camera_settings}"
            )

        return write_geo_knobs


    def process(self, instance):
        camera_node = instance.data["transientData"]["node"]
        handle_start = instance.context.data["handleStart"]
        handle_end = instance.context.data["handleEnd"]
        first_frame = int(nuke.root()["first_frame"].getValue())
        last_frame = int(nuke.root()["last_frame"].getValue())
        step = 1
        output_range = str(nuke.FrameRange(first_frame, last_frame, step))

        rm_nodes = []
        self.log.debug("Creating additional nodes for 3D Camera Extractor")
        product_name = instance.data["productName"]
        staging_dir = self.staging_dir(instance)

        # get extension form preset
        export_presets = self._get_camera_export_presets(instance)
        extension = next((k[1] for k in export_presets
                          if k[0] == "file_type"), None)
        if not extension:
            raise RuntimeError(
                "Bad config for extension in presets. "
                "Talk to your supervisor or pipeline admin")

        # create file name and path
        filename = product_name + ".{}".format(extension)
        file_path = os.path.join(staging_dir, filename).replace("\\", "/")

        with maintained_selection():
            # bake camera with axeses onto word coordinate XYZ
            rm_n = bakeCameraWithAxeses(
                camera_node, output_range)
            rm_nodes.append(rm_n)

            # create scene node
            rm_n = nuke.createNode("Scene")
            rm_nodes.append(rm_n)

            # create write geo node
            wg_n = nuke.createNode("WriteGeo")
            wg_n["file"].setValue(file_path)
            # add path to write to
            for k, v in export_presets:
                wg_n[k].setValue(v)
            rm_nodes.append(wg_n)

            # write out camera
            nuke.execute(
                wg_n,
                int(first_frame),
                int(last_frame)
            )
            # erase additional nodes
            for n in rm_nodes:
                nuke.delete(n)

        # create representation data
        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': extension,
            'ext': extension,
            'files': filename,
            "stagingDir": staging_dir,
            "frameStart": first_frame,
            "frameEnd": last_frame
        }
        instance.data["representations"].append(representation)

        instance.data.update({
            "path": file_path,
            "outputDir": staging_dir,
            "ext": extension,
            "handleStart": handle_start,
            "handleEnd": handle_end,
            "frameStart": first_frame + handle_start,
            "frameEnd": last_frame - handle_end,
            "frameStartHandle": first_frame,
            "frameEndHandle": last_frame,
        })

        self.log.debug("Extracted instance '{0}' to: {1}".format(
            instance.name, file_path))


def bakeCameraWithAxeses(camera_node, output_range):
    """ Baking all perent hierarchy of axeses into camera
    with transposition onto word XYZ coordinance
    """
    bakeFocal = False
    bakeHaperture = False
    bakeVaperture = False

    camera_matrix = camera_node['world_matrix']

    new_cam_n = nuke.createNode("Camera2")
    new_cam_n.setInput(0, None)
    new_cam_n['rotate'].setAnimated()
    new_cam_n['translate'].setAnimated()

    old_focal = camera_node['focal']
    if old_focal.isAnimated() and not (old_focal.animation(0).constant()):
        new_cam_n['focal'].setAnimated()
        bakeFocal = True
    else:
        new_cam_n['focal'].setValue(old_focal.value())

    old_haperture = camera_node['haperture']
    if old_haperture.isAnimated() and not (
            old_haperture.animation(0).constant()):
        new_cam_n['haperture'].setAnimated()
        bakeHaperture = True
    else:
        new_cam_n['haperture'].setValue(old_haperture.value())

    old_vaperture = camera_node['vaperture']
    if old_vaperture.isAnimated() and not (
            old_vaperture.animation(0).constant()):
        new_cam_n['vaperture'].setAnimated()
        bakeVaperture = True
    else:
        new_cam_n['vaperture'].setValue(old_vaperture.value())

    new_cam_n['win_translate'].setValue(camera_node['win_translate'].value())
    new_cam_n['win_scale'].setValue(camera_node['win_scale'].value())

    for x in nuke.FrameRange(output_range):
        math_matrix = nuke.math.Matrix4()
        for y in range(camera_matrix.height()):
            for z in range(camera_matrix.width()):
                matrix_pointer = z + (y * camera_matrix.width())
                math_matrix[matrix_pointer] = camera_matrix.getValueAt(
                    x, (y + (z * camera_matrix.width())))

        rot_matrix = nuke.math.Matrix4(math_matrix)
        rot_matrix.rotationOnly()
        rot = rot_matrix.rotationsZXY()

        new_cam_n['rotate'].setValueAt(math.degrees(rot[0]), x, 0)
        new_cam_n['rotate'].setValueAt(math.degrees(rot[1]), x, 1)
        new_cam_n['rotate'].setValueAt(math.degrees(rot[2]), x, 2)
        new_cam_n['translate'].setValueAt(
            camera_matrix.getValueAt(x, 3), x, 0)
        new_cam_n['translate'].setValueAt(
            camera_matrix.getValueAt(x, 7), x, 1)
        new_cam_n['translate'].setValueAt(
            camera_matrix.getValueAt(x, 11), x, 2)

        if bakeFocal:
            new_cam_n['focal'].setValueAt(old_focal.getValueAt(x), x)
        if bakeHaperture:
            new_cam_n['haperture'].setValueAt(old_haperture.getValueAt(x), x)
        if bakeVaperture:
            new_cam_n['vaperture'].setValueAt(old_vaperture.getValueAt(x), x)

    return new_cam_n
