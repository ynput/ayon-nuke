import os
import nuke
import pyblish.api

from ayon_core.pipeline import publish

from ayon_nuke import api as napi


class CollectNukeWrites(
    pyblish.api.InstancePlugin, publish.ColormanagedPyblishPluginMixin
):
    """Collect all write nodes."""

    order = pyblish.api.CollectorOrder + 0.0021
    label = "Collect Writes"
    hosts = ["nuke", "nukeassist"]
    families = ["render", "prerender", "image"]

    settings_category = "nuke"

    # cache
    _write_nodes = {}
    _frame_ranges = {}

    def process(self, instance):

        # compatibility. This is mainly focused on `renders`folders which
        # were previously not cleaned up (and could be used in read notes)
        # this logic should be removed and replaced with custom staging dir
        if instance.data.get("stagingDir_persistent") is None:
            instance.data["stagingDir_persistent"] = True

        group_node = instance.data["transientData"]["node"]

        render_target = instance.data["render_target"]

        write_node = self._write_node_helper(instance)

        if write_node is None:
            self.log.warning(
                "Created node '{}' is missing write node!".format(
                    group_node.name()
                )
            )
            return

        # get colorspace and add to version data
        colorspace = napi.get_colorspace_from_node(write_node)

        if render_target == "frames":
            self._set_existing_files_data(instance, colorspace)

        elif render_target == "frames_farm":
            collected_frames = self._set_existing_files_data(
                instance, colorspace
            )

            self._set_expected_files(instance, collected_frames)

            self._add_farm_instance_data(instance)

        if render_target == "farm":
            self._add_farm_instance_data(instance)

        # set additional instance data
        self._set_additional_instance_data(instance, render_target, colorspace)

    def _set_existing_files_data(self, instance, colorspace):
        """Set existing files data to instance data.

        Args:
            instance (pyblish.api.Instance): pyblish instance
            colorspace (str): colorspace

        Returns:
            list: collected frames
        """
        collected_frames = self._get_collected_frames(instance)

        representation = self._get_existing_frames_representation(
            instance, collected_frames
        )

        # inject colorspace data
        self.set_representation_colorspace(
            representation, instance.context, colorspace=colorspace
        )

        instance.data["representations"].append(representation)

        return collected_frames

    def _set_expected_files(self, instance, collected_frames):
        """Set expected files to instance data.

        Args:
            instance (pyblish.api.Instance): pyblish instance
            collected_frames (list): collected frames
        """
        write_node = self._write_node_helper(instance)

        write_file_path = nuke.filename(write_node)
        output_dir = os.path.dirname(write_file_path)

        instance.data["expectedFiles"] = [
            os.path.join(output_dir, source_file)
            for source_file in collected_frames
        ]

    def _get_frame_range_data(self, instance):
        """Get frame range data from instance.

        Args:
            instance (pyblish.api.Instance): pyblish instance

        Returns:
            tuple: first_frame, last_frame
        """

        instance_name = instance.data["name"]

        if self._frame_ranges.get(instance_name):
            # return cashed write node
            return self._frame_ranges[instance_name]

        write_node = self._write_node_helper(instance)

        # Get frame range from workfile
        first_frame = int(nuke.root()["first_frame"].getValue())
        last_frame = int(nuke.root()["last_frame"].getValue())

        # Get frame range from write node if activated
        if write_node["use_limit"].getValue():
            first_frame = int(write_node["first"].getValue())
            last_frame = int(write_node["last"].getValue())

        # add to cache
        self._frame_ranges[instance_name] = (first_frame, last_frame)

        return first_frame, last_frame

    def _set_additional_instance_data(
        self, instance, render_target, colorspace
    ):
        """Set additional instance data.

        Args:
            instance (pyblish.api.Instance): pyblish instance
            render_target (str): render target
            colorspace (str): colorspace
        """
        product_base_type = instance.data["productBaseType"]

        # add targeted family to families
        instance.data["families"].append(
            f"{product_base_type}.{render_target}"
        )
        self.log.debug(
            "Appending render target to families: {}.{}".format(
                product_base_type, render_target
            )
        )

        write_node = self._write_node_helper(instance)
        if instance.data.get("stagingDir_is_custom", False):
            self.log.info(
                "Custom staging dir detected. Syncing write nodes output path."
            )
            napi.lib.writes_version_sync(write_node, self.log)

        # Determine defined file type
        path = write_node["file"].value()
        ext = os.path.splitext(path)[1].lstrip(".")

        # determine defined channel type
        color_channels = write_node["channels"].value()

        # get frame range data
        handle_start = instance.context.data["handleStart"]
        handle_end = instance.context.data["handleEnd"]
        first_frame, last_frame = self._get_frame_range_data(instance)

        # get output paths
        write_file_path = nuke.filename(write_node)
        output_dir = os.path.dirname(write_file_path)

        # TODO: remove this when we have proper colorspace support
        version_data = {"colorspace": colorspace}

        if product_base_type == "plate":
            time_warp_node = _find_downstream_time_warp_node(
                instance.data["transientData"]["node"]
            )
            if time_warp_node:
                lookup_knob = time_warp_node["lookup"]
                version_data.update(
                    retime=True,
                    timewarps=(
                        dict(
                            Class=time_warp_node.Class(),
                            name=time_warp_node["name"].value(),
                            lookup=[
                                lookup_knob.valueAt(frame_number)
                                - frame_number
                                for frame_number in range(
                                    int(nuke.root()["first_frame"].getValue()),
                                    int(nuke.root()["last_frame"].getValue())
                                    + 1,
                                )
                            ],
                        ),
                    ),
                )

        instance.data.update(
            {
                "versionData": version_data,
                "path": write_file_path,
                "outputDir": output_dir,
                "ext": ext,
                "colorspace": colorspace,
                "color_channels": color_channels,
            }
        )

        if product_base_type == "render":
            instance.data.update(
                {
                    "handleStart": handle_start,
                    "handleEnd": handle_end,
                    "frameStart": first_frame + handle_start,
                    "frameEnd": last_frame - handle_end,
                    "frameStartHandle": first_frame,
                    "frameEndHandle": last_frame,
                }
            )
        else:
            instance.data.update(
                {
                    "handleStart": 0,
                    "handleEnd": 0,
                    "frameStart": first_frame,
                    "frameEnd": last_frame,
                    "frameStartHandle": first_frame,
                    "frameEndHandle": last_frame,
                }
            )

    def _write_node_helper(self, instance):
        """Helper function to get write node from instance.

        Also sets instance transient data with child nodes.

        Args:
            instance (pyblish.api.Instance): pyblish instance

        Returns:
            nuke.Node | None: write node
        """
        instance_name = instance.data["name"]

        if self._write_nodes.get(instance_name):
            # return cashed write node
            return self._write_nodes[instance_name]

        # get all child nodes from group node
        child_nodes = napi.get_instance_group_node_children(instance)

        # set child nodes to instance transient data
        instance.data["transientData"]["childNodes"] = child_nodes

        write_node = None
        for node_ in child_nodes:
            if node_.Class() == "Write":
                write_node = node_

        if write_node:
            # for slate frame extraction
            instance.data["transientData"]["writeNode"] = write_node
            # add to cache
            self._write_nodes[instance_name] = write_node

            return self._write_nodes[instance_name]

    def _get_existing_frames_representation(self, instance, collected_frames):
        """Get existing frames representation.

        Args:
            instance (pyblish.api.Instance): pyblish instance
            collected_frames (list): collected frames

        Returns:
            dict: representation
        """

        first_frame, last_frame = self._get_frame_range_data(instance)

        write_node = self._write_node_helper(instance)

        write_file_path = nuke.filename(write_node)
        output_dir = os.path.dirname(write_file_path)

        # Determine defined file type
        path = write_node["file"].value()
        ext = os.path.splitext(path)[1].lstrip(".")

        representation = {
            "name": ext,
            "ext": ext,
            "stagingDir": output_dir,
            "tags": [],
        }

        # set slate frame
        collected_frames = self._add_slate_frame_to_collected_frames(
            instance, collected_frames, first_frame
        )

        if len(collected_frames) == 1:
            representation["files"] = collected_frames.pop()
        else:
            representation["files"] = collected_frames

        return representation

    def _get_frame_start_str(self, first_frame, last_frame):
        """Get frame start string.

        Args:
            first_frame (int): first frame
            last_frame (int): last frame

        Returns:
            str: frame start string
        """
        # convert first frame to string with padding
        return ("{{:0{}d}}".format(len(str(last_frame)))).format(first_frame)

    def _add_slate_frame_to_collected_frames(
        self, instance, collected_frames, first_frame
    ):
        """Add slate frame to collected frames.

        Args:
            instance (pyblish.api.Instance): pyblish instance
            collected_frames (list): collected frames
            first_frame (int): first frame

        Returns:
            list: collected frames
        """
        if "slate" not in instance.data["families"]:
            return collected_frames

        write_node = self._write_node_helper(instance)
        expected_slate_frame = first_frame - 1
        expected_slate_path = write_node["file"].evaluate(expected_slate_frame)

        if not os.path.exists(expected_slate_path):
            slate_frame = os.path.basename(expected_slate_path)
            collected_frames.insert(0, slate_frame)

        return collected_frames

    def _add_farm_instance_data(self, instance):
        """Add farm publishing related instance data.

        Args:
            instance (pyblish.api.Instance): pyblish instance
        """

        # make sure rendered sequence on farm will
        # be used for extract review
        if not instance.data.get("review"):
            instance.data["useSequenceForReview"] = False

        # Farm rendering
        instance.data.update(
            {
                "transfer": False,
                "farm": True,  # to skip integrate
            }
        )
        self.log.info("Farm rendering ON ...")

    def _get_collected_frames(self, instance):
        """Get collected frames.

        Args:
            instance (pyblish.api.Instance): pyblish instance

        Returns:
            list: collected frames
        """

        first_frame, last_frame = self._get_frame_range_data(instance)

        write_node = self._write_node_helper(instance)

        write_file_path = nuke.filename(write_node)
        output_dir = os.path.dirname(write_file_path)

        # get file path knob
        node_file_knob = write_node["file"]
        # list file paths based on input frames
        expected_paths = list(
            sorted(
                {
                    node_file_knob.evaluate(frame)
                    for frame in range(first_frame, last_frame + 1)
                }
            )
        )

        # convert only to base names
        expected_filenames = {
            os.path.basename(filepath) for filepath in expected_paths
        }

        # make sure files are existing at folder
        collected_frames = [
            filename
            for filename in os.listdir(output_dir)
            if filename in expected_filenames
        ]

        return collected_frames


def _find_downstream_time_warp_node(start_node):
    # HACK: no idea why calling `dependentNodes` the first time
    # seems to always return nothing.
    nuke.dependentNodes(nuke.INPUTS, [start_node])
    for node in nuke.dependentNodes(nuke.INPUTS, [start_node]):
        if node.Class() == "TimeWarp":
            return node
