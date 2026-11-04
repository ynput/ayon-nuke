from __future__ import annotations

import pyblish.api
from typing import Any
import nuke
from ayon_nuke import api as napi


class CollectBurninMetadata(pyblish.api.InstancePlugin):
    """Collect Nuke metadata stream values as burnin/slate formatting keys.

    Metadata is read from the stream entering the instance's Write node
    (e.g. keys added upstream by a ModifyMetaData node such as
    `camera/focal` with an expression `[value Camera1.focal]`).

    Each configured entry is either an exact metadata key or a prefix
    ending with "/" (e.g. "camera/" collects every "camera/*" key).
    Collected keys are exposed unchanged, so `{camera/focal}` can be used
    in burnin templates and `{custom[camera/focal]}` in slate templates.

    Querying metadata makes Nuke validate the node graph for that frame,
    which can be slow on heavy comps. To avoid doing it for every frame,
    only the first, middle and last frames are sampled. The full frame
    range is evaluated only when the sampled values differ. A value
    animated only between the samples that ends up equal on all of them
    is reported as static.

    Burnins cannot change text per frame, so an animated value is
    reported as a range: "min-max" for numbers (e.g. "35-50"), otherwise
    "first-last" of the distinct values.
    """

    order = pyblish.api.CollectorOrder + 0.3
    label = "Collect Burnin Metadata"
    hosts = ["nuke", "nukeassist"]
    families = ["render", "prerender", "image"]

    settings_category = "nuke"

    metadata_keys = ["camera/"]

    def process(self, instance):
        if not self.metadata_keys:
            self.log.debug("No metadata keys configured. Skipping.")
            return

        write_node = self._get_write_node(instance)
        if write_node is None:
            self.log.debug(
                "No Write node found for instance '{}'. Skipping burnin "
                "metadata collection.".format(instance.data["name"])
            )
            return

        frame_start = int(instance.data.get("frameStartHandle", 1001))
        frame_end = int(instance.data.get("frameEndHandle", 1001))
        sample_frames = sorted({
            frame_start,
            (frame_start + frame_end) // 2,
            frame_end,
        })

        values_by_frame = {
            frame: self._get_requested_metadata(write_node, frame)
            for frame in sample_frames
        }

        if self._get_animated_keys(values_by_frame):
            self.log.debug(
                "Metadata differs between sampled frames {}. Evaluating "
                "frames {}-{} on '{}'.".format(
                    sample_frames, frame_start, frame_end,
                    write_node.fullName()
                )
            )
            for frame in range(frame_start, frame_end + 1):
                if frame not in values_by_frame:
                    values_by_frame[frame] = self._get_requested_metadata(
                        write_node, frame
                    )

        collected = {}
        all_frame_keys = sorted({
            key
            for values in values_by_frame.values()
            for key in values
        })

        for key in all_frame_keys:
            unique_values = {}
            for frame in sorted(values_by_frame):
                value = values_by_frame[frame].get(key)
                if value is not None:
                    unique_values.setdefault(value, None)

            if not unique_values:
                continue

            ordered = list(unique_values)
            collected[key] = (
                ordered[0] if len(ordered) == 1
                else self._format_range(ordered)
            )

        missing = {
            key for key in self.metadata_keys
            if not key.endswith("/") and key not in collected
        }
        if missing:
            self.log.debug(
                f"Metadata keys not found on '{write_node.fullName()}'"
                f" at frames {sample_frames}: {', '.join(sorted(missing))}"
            )

        if not collected:
            return

        instance.data.setdefault("burninDataMembers", {}).update(collected)

        self.log.debug("Collected burnin metadata: {}".format(collected))

    def _get_write_node(self, instance: pyblish.api.Instance) -> nuke.Node:
        """Get the Write node associated with the instance.

        Args:
            instance (pyblish.api.Instance): The instance to get the Write
                node for.

        Returns:
            nuke.Node: The associated Write node, or None if not found.
        """
        write_node = instance.data["transientData"].get("writeNode")
        if write_node is not None:
            return write_node

        for node in napi.get_instance_group_node_children(instance):
            if node.Class() == "Write":
                return node
        return None

    def _get_requested_metadata(
        self, write_node: nuke.Node, frame: int
    ) -> dict[str, str | int | bool | float | None]:
        """Read the requested metadata entering the Write node at a frame.

        Args:
            write_node (nuke.Node): The Write node to read metadata from.
            frame (int): The frame to evaluate the metadata at.

        Returns:
            dict[str, str | int | bool | float | None]: Requested metadata
                keys with normalized values.
        """
        metadata = write_node.metadata(time=frame)
        if not metadata:
            return {}
        return {
            key: self._normalize_value(value)
            for key, value in metadata.items()
            if self._is_requested(key)
        }

    @staticmethod
    def _get_animated_keys(
        values_by_frame: dict[int, dict[str, Any]]
    ) -> set[str]:
        """Get keys whose values differ between the given frames.

        Args:
            values_by_frame (dict[int, dict[str, Any]]): Metadata values
                per frame.

        Returns:
            set[str]: Keys with differing values (or missing on some frames).
        """
        all_values = list(values_by_frame.values())
        keys = {key for values in all_values for key in values}
        return {
            key for key in keys
            if len({repr(values.get(key)) for values in all_values}) > 1
        }

    @staticmethod
    def _format_range(values: list[Any]) -> str:
        """Format distinct values of an animated key as a range string.

        Args:
            values (list[Any]): Distinct values in frame order.

        Returns:
            str: "min-max" for numeric values, otherwise "first-last".
        """
        if all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in values
        ):
            return f"{min(values)}-{max(values)}"
        return f"{values[0]}-{values[-1]}"

    def _is_requested(self, key: str) -> bool:
        """Check if the metadata key is requested.

        Args:
            key (str): The metadata key to check.

        Returns:
            bool: True if the key is requested, False otherwise.
        """
        if any(char in key for char in "{}:[].!"):
            return False

        for requested in self.metadata_keys:
            if requested.endswith("/"):
                if key.startswith(requested):
                    return True
            elif key == requested:
                return True
        return False

    @staticmethod
    def _normalize_value(
        value: Any) -> str | int | bool | float | None:
        """Normalize the value to a string, integer, boolean, or float.

        Args:
            value (Any): The value to normalize.

        Returns:
            str | int | bool | float | None: The normalized
                string value, integer, boolean, float, or None.
        """
        if isinstance(value, (bool, int, float, str)) or value is None:
            return value
        return str(value)
