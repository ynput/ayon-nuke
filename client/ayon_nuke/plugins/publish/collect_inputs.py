from collections import deque


import pyblish.api
from ayon_core.pipeline import (
    registered_host,
    get_current_context
)


class CollectUpstreamInputs(pyblish.api.InstancePlugin):
    """Collect source input containers used for this publish.

    This will include `inputs` data of which loaded publishes were used in the
    generation of this publish. This leaves an upstream trace to what was used
    as input.

    """

    label = "Collect Inputs"
    order = pyblish.api.CollectorOrder + 0.2
    hosts = ["nuke", "nukeassist"]
    families = ["render", "image", "model", "source", "camera"]

    def process(self, instance):

        context = get_current_context()
        project_name = context["project_name"]
        folder_path = context["folder_path"]
        folder_name = folder_path.split("/")[-1]

        cache_key = "__cache_containers"
        pretty_key = "inputRepresentationNames"
        scene_containers = instance.context.data.get(cache_key, None)
        if scene_containers is None:
            # Query the scenes' containers if there's no cache yet
            host = registered_host()
            scene_containers = list(host.ls())
            for container in scene_containers:
                pretty_name = []
                _project = container.get("project_name", "")
                if _project != project_name:
                   pretty_name.append(_project)
                _namespace = container.get("namespace", "")
                if _namespace != folder_name:
                    pretty_name.append(_namespace)
                pretty_name.append(container.get("name", ""))
                pretty_name.append("v" + container.get("version", ""))
                container["pretty_name"] = "-".join(pretty_name)
            instance.context.data[cache_key] = scene_containers

        if scene_containers:
            inputs = [c["representation"] for c in scene_containers]
            instance.data["inputRepresentations"] = inputs
            self.log.debug("Collected inputs: %s" % inputs)

            names = [c["pretty_name"] for c in scene_containers]
            names_str = " ".join(names)
            instance.context.data[pretty_key] = names_str
            self.log.debug("Collected input names: %s" % names_str)
