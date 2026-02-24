from __future__ import annotations

import os
import nuke
import pyblish.api

from ayon_core.pipeline import publish

from ayon_nuke import api as napi


class CollectNukeWrites(
    pyblish.api.InstancePlugin, publish.ColormanagedPyblishPluginMixin
):
    """Collect all write nodes.

    This plugin collect the following data:

    - the "main" write node
       >>> instance.data["transientData"]["writeNode"] = nuke.Node
    - list of all write nodes for this instance (in case of multi-write nodes)
       >>> instance.data["transientData"]["writeNodes"] = list[nuke.Node]
    - expected files for the instance
       >>> instance.data["expectedFiles"] = list[str]

    """

    order = pyblish.api.CollectorOrder + 0.0021
    label = "Collect Writes"
    hosts = ["nuke", "nukeassist"]
    families = ["render", "prerender", "image"]

    settings_category = "nuke"

    # write node classes to collect
    write_node_classes = ["Write"]

    def process(self, instance) -> None:

        # compatibility. This is mainly focused on `renders`folders which
        # were previously not cleaned up (and could be used in read notes)
        # this logic should be removed and replaced with custom staging dir
        if instance.data.get("stagingDir_persistent") is None:
            instance.data["stagingDir_persistent"] = True

        group_node: nuke.Node = instance.data["transientData"]["node"]

        child_nodes = napi.get_instance_group_node_children(instance)
        write_nodes = [
            node
            for node in child_nodes
            if node.Class() in self.write_node_classes
        ]
        instance.data["transientData"]["writeNodes"] = write_nodes

        if not write_nodes:
            msg = f"Created node '{group_node.name()}' is missing write node!"
            self.log.warning(msg)
            return

        # todo: come up with a better way to determine the "main" write node
        write_node = write_nodes[0]
        instance.data["transientData"]["writeNode"] = write_node

        # get colorspace and add to version data
        colorspace = napi.get_colorspace_from_node(write_node)

        self._collect_frame_range_data(instance)
        self._collect_expected_files(instance)

        if instance.data["render_target"] in ["frames", "frames_farm"]:
            self._add_farm_instance_data(instance)

        # set additional instance data
        self._set_additional_instance_data(instance, render_target, colorspace)

    def _collect_frame_range_data(self, instance: pyblish.api.Instance) -> None:
        """Collect frame range data.

        Args:
            instance (pyblish.api.Instance): pyblish instance

        """
        write_node = instance.data["transientData"]["writeNode"]

        # Check in order of priority:
        # - override set in the publish settings (TODO)
        # - local override on the node
        # - previously collected frame range (TODO)
        # - frame range from the workfile
        if write_node["use_limit"].getValue():
            first_frame = int(write_node["first"].getValue())
            last_frame = int(write_node["last"].getValue())
        else:
            first_frame = int(nuke.root()["first_frame"].getValue())
            last_frame = int(nuke.root()["last_frame"].getValue())

        # only collect handle data for render instances
        if instance.data["productType"] == "render":
            handle_start = instance.context.data.get("handleStart", 0)
            handle_end = instance.context.data.get("handleEnd", 0)
        else:
            handle_start = 0
            handle_end = 0

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

    def _collect_expected_files(self, instance: pyblish.api.Instance) -> None:
        """Collect expected files.

        Args:
            instance (pyblish.api.Instance): pyblish instance

        """
        node = instance.data["transientData"]["writeNode"]
        start = instance.data["frameStart"]  # range includes handles
        end = instance.data["frameEnd"]

        # based on the docs  `nuke.filename` accepts a frame number as an argument
        # but this did not work for me (vincent-u, 24.02.2026, Nuke 15.2)
        filename = nuke.filename(node)
        if not filename:
            instance.data["expectedFiles"] = []
            # note: not sure if this is the best way to handle this
            # if introduces inconsistencies with the "path" and "outputDir" data
            return

        if "%" in filename:
            instance.data["expectedFiles"] = [filename % frame for frame in range(start, end + 1)]
        else: 
            # single file
            # TODO: if start != end we could raise an error here
            # this however is not the responsibility of this plugin
            instance.data["expectedFiles"] = [filename]

        instance.data["path"] = filename
        instance.data["outputDir"] = os.path.dirname(filename)
        instance.data["ext"] = os.path.splitext(filename)[1].lstrip(".")

    def _collect_colorspace_data(self, instance: pyblish.api.Instance) -> None:
        """Collect colorspace data.

        Args:
            instance (pyblish.api.Instance): pyblish instance

        """
        write_node = instance.data["transientData"]["writeNode"]
        colorspace = napi.get_colorspace_from_node(write_node)
        instance.data["colorspace"] = colorspace
        instance.data["color_channels"] = write_node["channels"].value()
        instance.data["versionData"] = {"colorspace": colorspace}

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
        self.log.debug("Appending render target to families: {}.{}".format(
            product_base_type, render_target)
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
        version_data = {
            "colorspace": colorspace
        }

        instance.data.update({
            "versionData": version_data,
            "path": write_file_path,
            "outputDir": output_dir,
            "ext": ext,
            "colorspace": colorspace,
            "color_channels": color_channels
        })

        if product_base_type == "render":
            instance.data.update({
                "handleStart": handle_start,
                "handleEnd": handle_end,
                "frameStart": first_frame + handle_start,
                "frameEnd": last_frame - handle_end,
                "frameStartHandle": first_frame,
                "frameEndHandle": last_frame,
            })
        else:
            instance.data.update({
                "handleStart": 0,
                "handleEnd": 0,
                "frameStart": first_frame,
                "frameEnd": last_frame,
                "frameStartHandle": first_frame,
                "frameEndHandle": last_frame,
            })

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

    def _get_existing_frames_representation(
        self,
        instance,
        collected_frames
    ):
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
            "tags": []
        }

        # set slate frame
        collected_frames = self._add_slate_frame_to_collected_frames(
            instance,
            collected_frames,
            first_frame
        )

        if len(collected_frames) == 1:
            representation['files'] = collected_frames.pop()
        else:
            representation['files'] = collected_frames

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
        return (
            "{{:0{}d}}".format(len(str(last_frame)))
        ).format(first_frame)

    def _add_slate_frame_to_collected_frames(
        self,
        instance,
        collected_frames,
        first_frame
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
