import re
from collections import defaultdict

import nuke
import pyblish.api

from ayon_core.pipeline import registered_host
from ayon_nuke.api.lib import (
    get_backdrop_nodes,
    get_container_members,
    get_viewer_input_process_node,
    iter_upstream_nodes,
)


class CollectUpstreamInputs(pyblish.api.ContextPlugin):
    """Collect source input containers used for this publish.

    This will include `inputs` data of which loaded publishes were used in the
    generation of this publish. This leaves an upstream trace to what was used
    as input.

    For each instance, the node graph is walked upstream from the instance's
    nodes through inputs and hidden inputs, into and out of groups. Loaded
    containers found on the way are the instance's inputs. When the Viewer
    input process node is baked into the instance's review, its upstream
    containers are included too.

    The workfile instance is skipped.

    This is a context plugin so the scene's containers are queried only once
    and the upstream dependencies of nodes are shared between instances,
    because both can be slow in heavy scripts.

    """

    label = "Collect Inputs"
    # Run after `CollectBackdrops` and before core's
    # `CollectInputRepresentationsToVersions`
    order = pyblish.api.CollectorOrder + 0.4
    hosts = ["nuke"]

    settings_category = "nuke"

    def process(self, context):
        instances = [
            instance for instance in context
            if instance.data.get("publish", True)
        ]
        if not instances:
            return

        host = registered_host()
        containers = list(host.get_containers())

        # Map nodes to the containers they are a member of
        containers_by_node = defaultdict(list)
        for container in containers:
            for member in get_container_members(container):
                containers_by_node[member].append(container)

        dependencies_cache = {}
        for instance in instances:
            nodes = self.get_instance_nodes(instance)
            if not nodes:
                continue

            # Use dict as ordered set of representation ids
            inputs = {}
            if containers_by_node:
                for node in iter_upstream_nodes(nodes, dependencies_cache):
                    for container in containers_by_node.get(node, []):
                        inputs[container["representation"]] = None
            inputs = list(inputs)

            instance.data["inputRepresentations"] = inputs
            self.log.debug(
                f"Collected inputs for {instance}: {inputs}"
            )

    def get_instance_nodes(self, instance):
        """Return the nodes of an instance to walk upstream from.

        Args:
            instance (pyblish.api.Instance): The instance.

        Returns:
            list[nuke.Node]: The instance's nodes.
        """
        node = instance.data["transientData"].get("node")
        if node is None or node.Class() == "Root":
            # The workfile instance uses the root node
            return []

        nodes = [node]
        if node.Class() == "BackdropNode":
            child_nodes = instance.data["transientData"].get("childNodes")
            if child_nodes is None:
                child_nodes = get_backdrop_nodes(node)
            nodes.extend(child_nodes)
        elif isinstance(node, nuke.Group):
            # Include all nodes of the group, e.g. of a write group, not just
            # the ones connected to its output node
            nodes.extend(nuke.allNodes(group=node, recurseGroups=True))

        if self.bakes_viewer_input_process(instance):
            try:
                input_process_node = get_viewer_input_process_node()
            except NameError as exc:
                # Extracting the review will fail on this, so we just log it
                self.log.warning(exc)
                input_process_node = None
            if input_process_node is not None:
                self.log.debug(
                    f"Including Viewer input process node "
                    f"'{input_process_node.fullName()}' for {instance}"
                )
                nodes.append(input_process_node)

        return nodes

    def bakes_viewer_input_process(self, instance):
        """Return whether the instance's review bakes the Viewer input process.

        This matches the filtering of baking outputs by
        `ExtractReviewIntermediates` and the fallback of `ExtractSlateFrame`
        when no output matched.

        Args:
            instance (pyblish.api.Instance): The instance.

        Returns:
            bool: Whether the Viewer input process node is baked.
        """
        families = set(instance.data.get("families", []))
        families.add(instance.data.get("productBaseType"))

        settings = (
            instance.context.data["project_settings"]
            ["nuke"]["publish"].get("ExtractReviewIntermediates", {})
        )
        has_outputs = False
        if "review" in families and settings.get("enabled", True):
            task_type = instance.context.data.get("taskType")
            product_name = instance.data["productName"]
            for output in settings.get("outputs", []):
                output_filter = output["filter"]
                product_base_types = output_filter["product_base_types"]
                task_types = output_filter["task_types"]
                product_names = output_filter["product_names"]
                if (
                    product_base_types
                    and not families.intersection(product_base_types)
                ):
                    continue
                if task_types and task_type not in task_types:
                    continue
                if product_names and not any(
                    re.search(name, product_name) for name in product_names
                ):
                    continue

                has_outputs = True
                if (
                    output["bake_viewer_process"]
                    and output["bake_viewer_input_process"]
                ):
                    return True

        if has_outputs:
            return False

        # Without baking outputs `ExtractSlateFrame` bakes the input process
        # into the slate frame by default
        return (
            instance.data.get("slateNode") is not None
            and not instance.data.get("farm")
        )
