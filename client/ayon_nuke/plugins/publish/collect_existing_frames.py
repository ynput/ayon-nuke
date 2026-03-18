"""
    UNTESTED !

    just copy pasted the relevant code from collect_writes.py

"""

from __future__ import annotations

import os
import nuke
import pyblish.api

from ayon_core.pipeline import publish

from ayon_nuke import api as napi


class CollectNukeExistingFrames(
    pyblish.api.InstancePlugin,
    publish.ColormanagedPyblishPluginMixin,
):
    """Collect existing frames.
    """

    order = pyblish.api.CollectorOrder + 0.0022
    label = "Collect Existing Frames"
    hosts = ["nuke", "nukeassist"]
    families = ["render", "prerender", "image"]

    settings_category = "nuke"

    def process(self, instance) -> None:


        render_target = instance.data["render_target"]

        if render_target not in ["frames", "frames_farm"]:
            return

        colorspace = 
        self._set_existing_files_data(instance, colorspace)



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
            representation, instance.context,
            colorspace=colorspace
        )

        instance.data["representations"].append(representation)

        return collected_frames

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
        expected_paths = list(sorted({
            node_file_knob.evaluate(frame)
            for frame in range(first_frame, last_frame + 1)
        }))

        # convert only to base names
        expected_filenames = {
            os.path.basename(filepath)
            for filepath in expected_paths
        }

        # make sure files are existing at folder
        collected_frames = [
            filename
            for filename in os.listdir(output_dir)
            if filename in expected_filenames
        ]

        return collected_frames


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


