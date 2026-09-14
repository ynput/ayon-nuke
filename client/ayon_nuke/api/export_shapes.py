import uuid
from typing import Union
import nuke
import nuke.rotopaint
import nukescripts
import xml.etree.ElementTree as ET
from ayon_core.pipeline.publish import PublishError


class ExportSilhouetteShapes:
    """Class for exporting silhouette shapes from Nuke roto nodes.

    This class handles the process of exporting silhouette shapes from Nuke
    roto nodes into an FXS XML structure, with options to bake shapes and
    manage transforms.

    Export Silhouette FXS shape data from Nuke Roto and RotoPaint nodes.

    This module contains adapted code from the Silhouette FXS Exporter for
    Nuke,originally authored by Magno Borgo and contributors. These codes
    are refactored and integrated into this module. Thank you to the original
    authors for their contributions.

    The original work is distributed under the BSD 3-Clause License.
    Its copyright notice, license terms, and disclaimer are retained in
    this project's third-party notices.
    See: https://github.com/magnoborgo/NukeFXSExporter


    """

    def __init__(
        self,
        start_frame: int,
        end_frame: int,
        bake_shapes: bool
    ) -> None:
        """Initialize the ExportSilhouetteShapes instance.

        Args:
            start_frame (int): The start frame of the frame range.
            end_frame (int): The end frame of the frame range.
            bake_shapes (bool): Whether to bake the shapes into the FXS layer.

        """
        self._frame_range = nuke.FrameRange(start_frame, end_frame, 1)
        self._bake_shapes = bake_shapes

        # state populated in process()
        self._root_node = None
        self._fxs_elem = None
        self._shape_list = None
        self._node_format = None
        self._roto_root = None

        self.process()

    def process(self) -> None:
        """Create a copy of the selected node and generate the fxs
        tree data."""
        nukescripts.node_copypaste()
        self._root_node = root_node = nuke.selectedNode()
        roto_curve = root_node["curves"]
        self._roto_root = roto_curve.rootLayer

        root_shapes = self._roto_paint_recursive(self._roto_root)
        self._make_shapes_unique(root_shapes)

        if not self._bake_shapes:
            self._manage_transforms(self._frame_range, root_node, root_shapes)

        roto_curve.changed()

        self._shape_list = self._roto_paint_recursive(self._roto_root)
        self._node_format = root_node["format"].value()

        fxs_initial_dictionary = {
            "width": str(self._node_format.width()),
            "height": str(self._node_format.height()),
            "workRangeStart": str(self._frame_range.first()),
            "workRangeEnd": str(self._frame_range.last()),
            "sessionStartFrame": str(self._frame_range.first()),
        }
        self._fxs_elem = ET.Element("Silhouette", fxs_initial_dictionary)

        layer_kwargs = {
            "roto_item": [self._roto_root, self._roto_root],
            "frame_range": self._frame_range,
            "roto_node": root_node,
            "shape_list": self._shape_list,
            "fxs_elem": self._fxs_elem,
            "bake_shapes": self._bake_shapes,
        }

        self._create_layers(**layer_kwargs)

        for shape_item in self._shape_list:
            if isinstance(shape_item[0], nuke.rotopaint.Layer):
                layer_kwargs["roto_item"] = shape_item
                self._create_layers(**layer_kwargs)

        self._reorganize_layers()

    def export(self, path: str) -> None:
        """Export the generated FXS tree to the specified file path.

        Args:
            path (str): The file path where the FXS tree should be exported.
        """
        if self._fxs_elem is None:
            raise PublishError(
                "Nothing to export - process() did not produce an FXS tree."
            )
        self._indent(self._fxs_elem)
        ET.ElementTree(self._fxs_elem).write(path)
        nuke.delete(self._root_node)

    def _indent(self, elems, level=0):
        """Indent the XML elements for pretty printing.

        Args:
            elems (xml.etree.ElementTree.Element): The XML element to indent.
            level (int, optional): The current indentation level.
                Defaults to 0.
        """
        i = "\n" + level * "  "
        if len(elems):
            if not elems.text or not elems.text.strip():
                elems.text = i + "  "
            if not elems.tail or not elems.tail.strip():
                elems.tail = i
            for elem in elems:
                self._indent(elem, level + 1)
            if not elems.tail or not elems.tail.strip():
                elems.tail = i
        else:
            if level and (not elems.tail or not elems.tail.strip()):
                elems.tail = i


    def _roto_paint_recursive(
        self,
        roto_root: Union[nuke.rotopaint.Layer, nuke.rotopaint.Shape]
    ) -> list:
        """Recursively traverse the roto node hierarchy and collect all
        shapes and layers.

        Args:
            roto_root (Union): The root layer or shape to start the
            traversal from.

        Returns:
            list: A list of [item, parent] pairs representing the shapes
            and layers found.
        """
        shape_list = []
        for item in roto_root:
            if isinstance(item, nuke.rotopaint.Shape):
                shape_list.append([item, roto_root])
            if isinstance(item, nuke.rotopaint.Layer):
                shape_list.append([item, roto_root])
                shape_list.extend(self._roto_paint_recursive(item))
        return shape_list

    @staticmethod
    def _make_shapes_unique(shape_list: list) -> None:
        """Ensure that all shapes in the list have unique names.

        Args:
            shape_list (list): A list of [shape, parent] pairs representing
            the shapes and their parent layers.

        """
        unique_shapes = set()
        for shape, _ in shape_list:
            if shape.name not in unique_shapes:
                unique_shapes.add(shape.name)
            else:
                shape.name = f"{shape.name}_{str(uuid.uuid4())}"

    @staticmethod
    def _check_transform_is_equal(
        shape_a: nuke.rotopaint.Shape,
        shape_b: nuke.rotopaint.Shape,
        frame_range: list
    ) -> bool:
        """Check if the transforms of two shapes are equal over a given
        frame range.

        Args:
            shape_a (nuke.rotopaint.Shape): The first shape to compare.
            shape_b (nuke.rotopaint.Shape): The second shape to compare.
            frame_range (list): The list of frames over which to compare
            the transforms.

        Returns:
            bool: True if the transforms are equal for all frames in the
            range, False otherwise.
        """
        for frame in frame_range:
            m1 = shape_a.getTransform().evaluate(frame).getMatrix()
            m2 = shape_b.getTransform().evaluate(frame).getMatrix()
            if m1 != m2:
                return False
        return True

    @classmethod
    def _manage_transforms(
        cls,
        frame_range: list,
        roto_node: nuke.Node,
        shape_list: list
    ) -> None:
        roto_curve = roto_node["curves"]
        created_shapes = []
        for shape_item in shape_list:
            if isinstance(shape_item[0], nuke.rotopaint.Shape):
                same_transform = False
                for shape in created_shapes:
                    if (
                        shape[1].name == shape_item[1].name
                        and cls._check_transform_is_equal(
                            shape_item[0], shape[0], frame_range
                        )
                    ):
                        same_transform = True
                        same_parent = shape[2]
                        break
                created_shapes.append(shape_item)
                shape_transform = shape_item[0].getTransform()
                if len(shape_item[1]) > 1:  # apply to a new layer
                    if not same_transform:
                        new_layer = nuke.rotopaint.Layer(roto_curve)
                        new_layer.name = shape_item[0].name + "_trkdata"
                        new_layer.setTransform(shape_transform)
                        shape_item[1].append(new_layer)
                        new_layer.append(shape_item[0])
                        created_shapes[-1].append(new_layer)
                    else:
                        same_parent.append(shape_item[0])
                else:
                    new_layer = nuke.rotopaint.Layer(roto_curve)
                    new_layer_transform = new_layer.getTransform()
                    matrixCurves = []
                    for i in range(4):
                        matrixCurves.append([])
                        for j in range(4):
                            matrixCurves[i].append(
                                new_layer_transform.getExtraMatrixAnimCurve(
                                    i, j
                                )
                            )
                    parent_transform = shape_item[1].getTransform()
                    for frame in frame_range:
                        m1 = shape_transform.evaluate(frame).getMatrix()
                        m2 = parent_transform.evaluate(frame).getMatrix()
                        m3 = m2 * m1
                        m = 0
                        for i in range(4):
                            for j in range(4):
                                matrixCurves[i][j].addKey(
                                    frame, m3.__getitem__(m)
                                )
                                m += 1
                    new_layer_transform = new_layer.getTransform()
                    shape_item[1].setTransform(new_layer_transform)

    @staticmethod
    def _parse_shape_flags(flags: int) -> list:
        """Parse the integer flags of a shape into a list of human-readable
        flag names.

        Args:
            flags (int): The integer flags of the shape.

        Returns:
            list: A list of human-readable flag names corresponding to the set
            bits in the integer flags.
        """
        flag_list = []
        nuke_flags = [
            "eBreakFlag",
            "eTangentLengthLockFlag",
            "eKeySelectedFlag",
            "eLeftTangentSelectedFlag",
            "eRightTangentSelectedFlag",
            "eOpenFlag",
            "eSelectedFlag",
            "eActiveFlag",
            "eVisibleFlag",
            "eRenderableFlag",
            "eLockedFlag",
            "ePressureInZFlag",
            "eNukeAnimCurveEvalFlag",
            "eRelativeTangentFlag",
        ]

        def get_bin(x, n):
            if x >= 0:
                return bin(x)[2:].zfill(n)
            else:
                return "-" + bin(x)[3:].zfill(n)

        bin_flags = get_bin(flags, len(nuke_flags))[::-1]
        for pos, bit in enumerate(bin_flags):
            if bit == "1":
                flag_list.append(nuke_flags[pos])
        return flag_list

    @classmethod
    def _transform_layers(
        cls,
        point: nuke.math.Vector4,
        layer: nuke.rotopaint.Layer,
        frame: int,
        roto_root: nuke.rotopaint.Layer,
        shape_list: list
    ) -> nuke.math.Vector4:
        """Recursively transform a point through the hierarchy of roto layers.

        Args:
            point (nuke.math.Vector4): The point to transform.
            layer (nuke.rotopaint.Layer): The current layer of the point.
            frame (int): The frame at which to evaluate the transforms.
            roto_root (nuke.rotopaint.Layer): The root layer of the roto node.
            shape_list (list): A list of shape-layer pairs representing the
                hierarchy.

        Returns:
            nuke.math.Vector4: The transformed point.
        """
        if layer == roto_root:
            transf = layer.getTransform()
            newpoint = cls._transform_to_matrix(point, transf, frame)
        else:
            transf = layer.getTransform()
            newpoint = cls._transform_to_matrix(point, transf, frame)
            for x in shape_list:  # look the layer parent
                if x[0] == layer:
                    newpoint = cls._transform_layers(
                        newpoint, x[1], frame, roto_root, shape_list
                    )
        return newpoint

    @staticmethod
    def _world_to_image_transform(
        point_value: float,
        node_format: nuke.Format,
        axis: str) -> float:
        """Convert a world coordinate to an image coordinate based on the node
        format and axis.

        Args:
            point_value (float): The world coordinate value.
            node_format (nuke.Format): The format of the node.
            axis (str): The axis to transform ("x" or "y").

        Returns:
            float: The transformed image coordinate.
        """
        if axis == "x":
            distance = (
                point_value - (node_format.width() / 2)
            ) / node_format.height()
            transform = distance * node_format.pixelAspect()
        else:
            distance = (node_format.height() - point_value) - (
                node_format.height() / 2
            )
            transform = distance / node_format.height()
        return transform

    @staticmethod
    def _transform_to_matrix(
        point: list,
        transform: nuke.Transform,
        frame: float
    ) -> nuke.math.Vector4:
        """Transform a point using the given transformation matrix and frame.

        Args:
            point (list): The point to transform.
            transform (nuke.Transform): The transformation to apply.
            frame (float): The frame number for the transformation.

        Returns:
            nuke.math.Vector4: The transformed point.
        """
        extra_matrix = transform.evaluate(frame).getMatrix()
        vector = nuke.math.Vector4(point[0], point[1], 1, 1)

        x = (
            (vector[0] * extra_matrix[0])
            + (vector[1] * extra_matrix[1])
            + extra_matrix[2]
            + extra_matrix[3]
        )
        y = (
            (vector[0] * extra_matrix[4])
            + (vector[1] * extra_matrix[5])
            + extra_matrix[6]
            + extra_matrix[7]
        )
        z = (
            (vector[0] * extra_matrix[8])
            + (vector[1] * extra_matrix[9])
            + extra_matrix[10]
            + extra_matrix[11]
        )
        w = (
            (vector[0] * extra_matrix[12])
            + (vector[1] * extra_matrix[13])
            + extra_matrix[14]
            + extra_matrix[15]
        )
        vector = nuke.math.Vector4(x, y, z, w)
        vector = vector / w
        return vector

    @classmethod
    def _matrix_to_layer(
        cls,
        item: tuple,
        frame_range: list,
        roto_node: nuke.rotopaint.Layer,
        fxs_layer: ET.Element
    ) -> None:
        """Convert a transformation matrix to a layer representation for the
        given frame range and roto node.

        Args:
            item (tuple): The item containing the transformation to apply.
            frame_range (list): The range of frames to process.
            roto_node (nuke.rotopaint.Layer): The roto node containing the
                layer.
            fxs_layer (ET.Element): The XML element representing the layer in
                the FXS format.

        """
        projection_matrix_to = nuke.math.Matrix4()
        projection_matrix_from = nuke.math.Matrix4()
        node_format = roto_node["format"].value()
        transform = item[0].getTransform()
        transform_matrix_fsx = ET.SubElement(
            fxs_layer, "Property", {"id": "transform.matrix"}
        )
        for frame in frame_range:
            to_first = [0.0, 0.0]
            to_second = [float(node_format.width()), 0.0]
            to_third = [
                float(node_format.width()),
                float(node_format.height())
            ]
            to_fourth = [0.0, float(node_format.height())]
            to_first = cls._transform_to_matrix(to_first, transform, frame)
            to_second = cls._transform_to_matrix(to_second, transform, frame)
            to_third = cls._transform_to_matrix(to_third, transform, frame)
            to_fourth = cls._transform_to_matrix(to_fourth, transform, frame)

            to_first_x = cls._world_to_image_transform(
                to_first[0], node_format, "x"
            )
            to_second_x = cls._world_to_image_transform(
                to_second[0], node_format, "x"
            )
            to_third_x = cls._world_to_image_transform(
                to_third[0], node_format, "x"
            )
            to_fourth_x = cls._world_to_image_transform(
                to_fourth[0], node_format, "x"
            )
            to_first_y = cls._world_to_image_transform(
                to_first[1], node_format, "y"
            )
            to_second_y = cls._world_to_image_transform(
                to_second[1], node_format, "y"
            )
            to_third_y = cls._world_to_image_transform(
                to_third[1], node_format, "y"
            )
            to_fourth_y = cls._world_to_image_transform(
                to_fourth[1], node_format, "y"
            )

            from_first_x, from_first_y = [
                cls._world_to_image_transform(0.0, node_format, "x"),
                0.5,
            ]
            from_second_x, from_second_y = [
                cls._world_to_image_transform(
                    float(node_format.width()), node_format, "x"
                ),
                0.5,
            ]
            from_third_x, from_third_y = [
                cls._world_to_image_transform(
                    float(node_format.width()), node_format, "x"
                ),
                -0.5,
            ]
            from_fourth_x, from_fourth_y = [
                cls._world_to_image_transform(0.0, node_format, "x"),
                -0.5,
            ]
            projection_matrix_to.mapUnitSquareToQuad(
                to_first_x,
                to_first_y,
                to_second_x,
                to_second_y,
                to_third_x,
                to_third_y,
                to_fourth_x,
                to_fourth_y,
            )
            projection_matrix_from.mapUnitSquareToQuad(
                from_first_x,
                from_first_y,
                from_second_x,
                from_second_y,
                from_third_x,
                from_third_y,
                from_fourth_x,
                from_fourth_y,
            )
            concept_as_matrix = (
                projection_matrix_to * projection_matrix_from.inverse()
            )
            matrix_key_fsx = ET.SubElement(
                transform_matrix_fsx,
                "Key",
                {
                    "frame": str(frame - nuke.root().firstFrame()),
                    "interp": "linear",
                },
            )

            matrix_line = ""
            for n in range(len(concept_as_matrix)):
                matrix_line += f"{concept_as_matrix[n]:f} "
                if n < 15:
                    matrix_line += ","
            matrix_key_fsx.text = "(" + matrix_line + ")"

            layer_props = fxs_layer.findall(".//Property")
            list_to_remove = []
            for prop in layer_props:
                if prop.attrib.get("id") == "transform.matrix":
                    keys = prop.findall(".//Key")
                    if (
                        n > 0
                        and n < len(keys) - 1
                        and keys[n].text == keys[n - 1].text
                        and keys[n].text == keys[n + 1].text
                    ):
                        list_to_remove.append(n)
            main_path = fxs_layer.findall(".//Property")
            for prop in main_path:
                if prop.attrib.get("id") == "transform_matrix":
                    keys = prop.findall(".//Key")
                    last_key_idx = len(keys) - 1
                    for key in keys[::-1]:
                        if last_key_idx in list_to_remove:
                            prop.remove(key)
                        last_key_idx -= 1

    @classmethod
    def _create_layers(cls, **kwargs):
        """Create FXS layers for the given roto item and shape list.

        Args:
            roto_item (tuple): The roto item containing the layer information.
            frame_range (list): The range of frames to process.
            roto_node (nuke.rotopaint.Layer): The roto node containing the
                layer.
            shape_list (list): The list of shapes to export.
            fxs_elem (ET.Element): The XML element representing the FXS
                structure.
            bake_shapes (bool): Whether to bake the shapes into the FXS layer.
        """
        roto_item = kwargs.get("roto_item")
        frame_range = kwargs.get("frame_range")
        roto_node = kwargs.get("roto_node")
        shape_list = kwargs.get("shape_list")
        fxs_elem = kwargs.get("fxs_elem")
        bake_shapes = kwargs.get("bake_shapes")
        fxs_layer = cls._create_fxs_layer(roto_item, fxs_elem)
        fxs_properties = ET.SubElement(fxs_layer, "Properties")

        fxs_color = ET.SubElement(
            fxs_properties, "Property", {"id": "color", "value": "#FFFFFF"}
        )
        fxs_color_value = ET.SubElement(fxs_color, "Value")
        fxs_color_value.text = "(1.000000,1.000000,1.000000)"

        fxs_invert = ET.SubElement(
            fxs_properties, "Property", {"constant": "True", "id": "invert"}
        )
        fxs_invent_value = ET.SubElement(fxs_invert, "Value")
        fxs_invent_value.text = "false"

        fxs_mode = ET.SubElement(
            fxs_properties, "Property", {"constant": "True", "id": "mode"}
        )
        fxs_mode_value = ET.SubElement(fxs_mode, "Value")
        fxs_mode_value.text = "Add"

        ET.SubElement(
            fxs_properties,
            "Property",
            {"id": "objects", "constant": "True", "expanded": "True"},
        )

        if not bake_shapes:
            cls._matrix_to_layer(
                roto_item, frame_range, roto_node, fxs_properties
            )

        for shape_item in shape_list[::-1]:
            if (
                isinstance(shape_item[0], nuke.rotopaint.Shape)
                and shape_item[1].name == roto_item[0].name
            ):
                cls._create_fxs_shape(
                    shape_item,
                    frame_range,
                    roto_node,
                    shape_list,
                    fxs_elem,
                    bake_shapes,
                )

    @classmethod
    def _create_fxs_shape(
        cls,
        shape_item: tuple,
        frame_range: list,
        roto_node: nuke.rotopaint.Layer,
        shape_list: list,
        fxs_elem: ET.Element,
        bake_shapes: bool
    ) -> None:
        """Create an FXS shape element for the given shape item.

        Args:
            shape_item (tuple): The shape item containing the shape
                information.
            frame_range (list): The range of frames to process.
            roto_node (nuke.rotopaint.Layer): The roto node containing
                the layer.
            shape_list (list): The list of shapes to export.
            fxs_elem (ET.Element): The XML element representing
                the FXS structure.
            bake_shapes (bool): Whether to bake the shapes into the FXS layer.
        """
        if len(shape_item[0]) <= 1:
            return

        curve_type = ""
        shape_raw_info = shape_item[0].serialise()
        shape_raw_info = shape_raw_info.split("\n")
        if any(
            string
            for string in ["{curvegroup ", "{cubiccurve "]
            if shape_raw_info[0].count(string) > 0
        ):
            curve = shape_raw_info[0].split()
            curve_type = curve[3]

        shape_type = "Bezier" if curve_type == "bezier" else "Bspline"

        try:
            shape_flags = int(shape_raw_info[0].split()[2])
        except Exception as e:
            raise e

        shape_flags = cls._parse_shape_flags(shape_flags)
        cc_shape_flags = shape_raw_info[2]
        cc_shape_flags = int(cc_shape_flags[1:-1].split()[1])
        cc_shape_flags = cls._parse_shape_flags(cc_shape_flags)

        roto_curve = roto_node["curves"]
        roto_root = roto_curve.rootLayer
        all_shape_attributes = shape_item[0].getAttributes()

        hidden_attr = (
            "True" if all_shape_attributes.getValue(0, "vis") == 0 else "False"
        )
        locked_attr = "True" if "eLockedFlag" in shape_flags else "False"

        layer_list = fxs_elem.findall("Layer")
        layer_is_matched = False
        fxs_shape = None
        for layer in layer_list:
            if layer.get("label") == shape_item[1].name:
                layer_is_matched = True
                object_list = layer.findall("Properties/Property")
                for obj_item in object_list:
                    if obj_item.get("id") == "objects":
                        fxs_shape = ET.SubElement(
                            obj_item,
                            "Object",
                            {
                                "type": "Shape",
                                "label": shape_item[0].name,
                                "shape_type": shape_type,
                                "hidden": hidden_attr,
                                "locked": locked_attr,
                            },
                        )
                break

        if not layer_is_matched:
            layer_list = fxs_elem.findall(".//Object")
            for layer_item in layer_list:
                if layer_item.get("label") == shape_item[1].name:
                    layer_is_matched = True
                    object_list = layer_item.findall("Properties/Property")
                    for obj_item in object_list:
                        if obj_item.get("id") == "objects":
                            fxs_shape = ET.SubElement(
                                obj_item,
                                "Object",
                                {
                                    "type": "Shape",
                                    "label": shape_item[0].name,
                                    "shape_type": shape_type,
                                    "hidden": hidden_attr,
                                    "locked": locked_attr,
                                },
                            )
                    break

        if fxs_shape is None:
            return

        fxs_properties = ET.SubElement(fxs_shape, "Properties")

        # opacity
        opcindex = 0
        for n in range(0, len(all_shape_attributes)):
            if all_shape_attributes.getName(n) == "opc":
                opcindex = n
                break
        number_of_keys = all_shape_attributes.getCurve("opc").getNumberOfKeys()
        if number_of_keys > 0:
            fxs_opacity = ET.SubElement(
                fxs_properties, "Property", {"id": "opacity"}
            )
            for key in range(0, number_of_keys):
                key_interpolation = (
                    all_shape_attributes.getCurve("opc")
                    .getKey(key)
                    .interpolationType
                )
                key_interpolation = (
                    "hold" if key_interpolation == 257 else "linear"
                )
                key_time = all_shape_attributes.getKeyTime(opcindex, key)
                fxs_opc_key = ET.SubElement(
                    fxs_opacity,
                    "Key",
                    {
                        "frame": str(key_time - nuke.root().firstFrame()),
                        "interp": key_interpolation,
                    },
                )
                fxs_opc_key.text = str(
                    all_shape_attributes.getValue(key_time, "opc") * 100
                )
        else:
            constant_key_time = all_shape_attributes.getKeyTime(opcindex, 0)
            fxs_opacity = ET.SubElement(
                fxs_properties,
                "Property",
                {"constant": "True", "id": "opacity"},
            )
            fxs_opc_value = ET.SubElement(fxs_opacity, "Value")
            fxs_opc_value.text = str(
                all_shape_attributes.getValue(constant_key_time, "opc") * 100
            )

        # motion blur
        fxs_motion_blur = ET.SubElement(
            fxs_properties,
            "Property",
            {"constant": "True", "id": "motionBlur"}
        )
        fxs_motion_blur_value = ET.SubElement(fxs_motion_blur, "Value")
        fxs_motion_blur_value.text = (
            "false"
            if all_shape_attributes.getValue(0, "mbo") == 0
            else "true"
        )

        # shape overlay color
        fxs_outline_color = ET.SubElement(
            fxs_properties,
            "Property",
            {"constant": "True", "id": "outlineColor"},
        )
        fxs_outline_color_value = ET.SubElement(fxs_outline_color, "Value")

        r = all_shape_attributes.getValue(0, "ro")
        g = all_shape_attributes.getValue(0, "go")
        b = all_shape_attributes.getValue(0, "bo")
        if r == 0.0 and g == 0.0 and b == 0.0:
            fxs_outline_color_value.text = "(1.0, 0.0, 0.0)"
        else:
            fxs_outline_color_value.text = (
                "(" + str(r) + ", " + str(g) + ", " + str(b) + ")"
            )

        # blending mode
        fxs_blending_mode = ET.SubElement(
            fxs_properties, "Property", {"constant": "True", "id": "mode"}
        )
        fxs_blending_mode_value = ET.SubElement(fxs_blending_mode, "Value")
        modes = {
            0: "Add",
            12: "Subtract",
            13: "Difference",
            4: "Max",
            5: "Inside",
        }
        blending_mode = all_shape_attributes.getValue(0, "bm")
        if modes.get(blending_mode) is not None:
            fxs_blending_mode_value.text = modes.get(blending_mode)
        else:
            fxs_blending_mode_value.text = "Add"

        # shape inverted
        fxs_invert = ET.SubElement(
            fxs_properties, "Property", {"constant": "True", "id": "invert"}
        )
        fxs_inverted_value = ET.SubElement(fxs_invert, "Value")
        fxs_inverted_value.text = (
            "true" if all_shape_attributes.getValue(0, "inv") == 1 else "false"
        )

        fxs_path = ET.SubElement(fxs_properties, "Property", {"id": "path"})
        path_is_closed = "eOpenFlag" not in cc_shape_flags
        idx = 0
        accept = True
        key_frame_times = {}

        for point in shape_item[0]:
            pts = [
                point.center.getPositionAnimCurve(0),
                point.center.getPositionAnimCurve(1),
                point.leftTangent.getPositionAnimCurve(0),
                point.leftTangent.getPositionAnimCurve(1),
                point.rightTangent.getPositionAnimCurve(0),
                point.rightTangent.getPositionAnimCurve(1),
            ]
            for curve in pts:
                num_keys = curve.getNumberOfKeys()
                for idx in range(num_keys):
                    k = curve.getKey(idx)
                    time = k.time
                    if time not in key_frame_times:
                        key_frame_times[time] = True
                        continue
                    if key_frame_times[time]:
                        accept = False

                        if idx > 0:
                            prev = curve.getKey(idx - 1)
                            if prev.rslope == k.lslope:
                                accept = True
                            if k.interpolationType in ("257", "258"):
                                accept = True
                    elif idx == 0:
                        if (num_keys == 1) or (
                            k.rslope == curve.getKey(idx + 1).lslope
                            and k.interpolationType in (256, 257, 258)
                        ):
                            accept = True

                    if not accept:
                        key_frame_times[time] = False
                idx += 1

        keys = sorted(key_frame_times.items(), key=lambda x: x[0])

        for key in range(len(keys))[::-1]:
            if keys[key][0] < int(frame_range.first()):
                keys.pop(key)

        if len(keys) == 0:
            keys.append([frame_range.first(), True])

        idx = 0
        node_format = roto_node["format"].value()
        n = 0
        remove_list = []
        for frame in frame_range:
            if n >= len(keys):
                break
            is_before_or_equal = not keys[n][1] and frame <= keys[n][0]
            is_exact_match = keys[n][1] and frame == keys[n][0]
            is_boundary = frame in (frame_range.first(), frame_range.last())
            if is_before_or_equal or is_exact_match or is_boundary:
                fxs_path_key = ET.SubElement(
                    fxs_path,
                    "Key",
                    {
                        "frame": str(frame - nuke.root().firstFrame()),
                        "interp": "linear",
                    },
                )
                fxs_path_key_path = ET.SubElement(
                    fxs_path_key,
                    "Path",
                    {"closed": str(path_is_closed), "type": shape_type},
                )
                for point in shape_item[0]:
                    point_c = [
                        point.center.getPositionAnimCurve(0).evaluate(frame),
                        point.center.getPositionAnimCurve(1).evaluate(frame),
                    ]
                    point_lt = [
                        point.center.getPositionAnimCurve(0).evaluate(frame)
                        + (
                            point.leftTangent.getPositionAnimCurve(0).evaluate(
                                frame
                            )
                            * -1
                        ),
                        point.center.getPositionAnimCurve(1).evaluate(frame)
                        + (
                            point.leftTangent.getPositionAnimCurve(1).evaluate(
                                frame
                            )
                            * -1
                        ),
                    ]
                    point_rt = [
                        point.center.getPositionAnimCurve(0).evaluate(frame)
                        + (
                            point.rightTangent.getPositionAnimCurve(0).evaluate(
                                frame
                            )
                            * -1
                        ),
                        point.center.getPositionAnimCurve(1).evaluate(frame)
                        + (
                            point.rightTangent.getPositionAnimCurve(1).evaluate(
                                frame
                            )
                            * -1
                        ),
                    ]
                    transf = shape_item[0].getTransform()
                    if bake_shapes:
                        point_c = cls._transform_to_matrix(
                            point_c, transf, frame
                        )
                        point_c = cls._transform_layers(
                            point_c, shape_item[1], frame,
                            roto_root, shape_list
                        )
                        point_lt = cls._transform_to_matrix(
                            point_lt, transf, frame
                        )
                        point_lt = cls._transform_layers(
                            point_lt, shape_item[1], frame,
                            roto_root, shape_list
                        )
                        point_rt = cls._transform_to_matrix(
                            point_rt, transf, frame
                        )
                        point_rt = cls._transform_layers(
                            point_rt, shape_item[1], frame,
                            roto_root, shape_list
                        )

                    x = point_c[0]
                    y = point_c[1]
                    ltx = point_lt[0]
                    rtx = point_rt[0]
                    lty = point_lt[1]
                    rty = point_rt[1]
                    x = cls._world_to_image_transform(x, node_format, "x")
                    y = cls._world_to_image_transform(y, node_format, "y")
                    ltx = cls._world_to_image_transform(ltx, node_format, "x")
                    lty = cls._world_to_image_transform(lty, node_format, "y")
                    rtx = cls._world_to_image_transform(rtx, node_format, "x")
                    rty = cls._world_to_image_transform(rty, node_format, "y")
                    fxsPoint = ET.SubElement(fxs_path_key_path, "Point")
                    if shape_type == "Bspline":
                        fxsPoint.text = f"({x:f},{y:f})"
                    else:
                        fxsPoint.text = (
                            f"({x:f},{y:f}),({rtx:f},{rty:f}),({ltx:f},{lty:f})"
                        )

            if frame == keys[n][0] and keys[n][0] != keys[-1][0]:
                idx += 1
                n += 1

        shape_path = fxs_shape.findall(".//Path")
        remove_list = []

        for m in range(1, len(shape_path) - 1):  # skip first and last
            actual = [cls._parse_point(p) for p in shape_path[m]]
            prev = [cls._parse_point(p) for p in shape_path[m - 1]]
            next_ = [cls._parse_point(p) for p in shape_path[m + 1]]
            if actual == prev == next_:
                remove_list.append(m)  # Fixed: append index, not element

        mainpath = fxs_shape.findall(".//Property")
        for prop in mainpath:
            if prop.attrib.get("id") == "path":
                keys_elems = prop.findall(".//Key")
                keysn = len(keys_elems) - 1
                for k in keys_elems[::-1]:
                    if keysn in remove_list:
                        prop.remove(k)
                    keysn -= 1

    @staticmethod
    def _parse_point(elem: ET.Element, precision: int = 3) -> tuple:
        """Convert '(x,y)' text into a rounded tuple of floats."""
        x, y = elem.text[1:-1].split(",")
        return (round(float(x), precision), round(float(y), precision))

    @classmethod
    def _create_fxs_layer(
        cls,
        roto_item: tuple,
        fxs_elem: ET.Element
    ) -> ET.Element:
        fxs_layer_elem = None
        if roto_item[0].name == roto_item[1].name:
            fxs_layer_elem = ET.SubElement(
                fxs_elem,
                "Layer",
                {
                    "type": "Layer",
                    "label": roto_item[0].name,
                    "expanded": "True",
                },
            )
        else:
            layer_is_matched = False
            layer_list = fxs_elem.findall(".//Object")
            for layer_item in layer_list:
                if layer_item.get("label") == roto_item[1].name:
                    layer_is_matched = True
                    layer_object = layer_item.findall("Properties/Property")
                    for obj_item in layer_object:
                        if obj_item.get("id") == "objects":
                            fxs_layer_elem = ET.SubElement(
                                obj_item,
                                "Object",
                                {
                                    "type": "Layer",
                                    "label": roto_item[0].name,
                                    "expanded": "True",
                                },
                            )
                            break
            if not layer_is_matched:
                layer_list = fxs_elem.findall(".//Layer")
                for layer_item in layer_list:
                    if layer_item.get("label") == roto_item[1].name:
                        layer_is_matched = True
                        layer_object = layer_item.findall(
                            "Properties/Property"
                        )
                        for obj_item in layer_object:
                            if obj_item.get("id") == "objects":
                                fxs_layer_elem = ET.SubElement(
                                    obj_item,
                                    "Object",
                                    {
                                        "type": "Layer",
                                        "label": roto_item[0].name,
                                        "expanded": "True",
                                    },
                                )
                                break
                        break
        return fxs_layer_elem

    def _reorganize_layers(self) -> None:
        """Reorganize the layers in the FXS element based on the shape list.

        This method rearranges the layers in the FXS XML element so that they
        follow the order of the shapes in the shape list, ensuring that all
        objects from the same parent layer are grouped together.
        """
        layer_list = []
        for item in self._shape_list[::-1]:
            if item[1].name not in layer_list:
                layer_list.append(item[1].name)

        for name in layer_list:
            data = []
            parent_element = []
            for item in self._shape_list[::-1]:
                if item[1].name == name:  # all items from same parent
                    for itemx in self._fxs_elem.findall(".//*"):
                        if (
                            itemx.get("label")
                            and item[0].name == itemx.get("label")
                            and itemx not in data
                        ):
                            data.append(itemx)
            for itemx in self._fxs_elem.findall(".//*"):
                if itemx.get("label") == name:
                    obj = itemx.findall("Properties/Property")
                    for item in obj:
                        if item.get("id") == "objects":
                            parent_element.append(item)
                            break
            for n in range(len(data)):
                parent_element[0][n] = data[n]
