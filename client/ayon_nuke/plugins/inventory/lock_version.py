from ayon_core.pipeline import InventoryAction
from ayon_nuke.api.lib import imprint


class LockVersions(InventoryAction):
    label = "Lock versions"
    icon = "lock"
    color = "#ffffff"
    order = -1

    @staticmethod
    def is_compatible(container):
        return container.get("version_locked") is not True

    def process(self, containers):
        import nuke

        for container in containers:
            if container.get("version_locked") is True:
                continue
            node = nuke.toNode(container["objectName"])
            container["version_locked"] = True
            imprint(node, {"avalon:version_locked": True})
            node["avalon:version_locked"].setLabel("Version locked")


class UnlockVersions(InventoryAction):
    label = "Unlock versions"
    icon = "lock-open"
    color = "#ffffff"
    order = -1

    @staticmethod
    def is_compatible(container):
        return container.get("version_locked") is True

    def process(self, containers):
        import nuke

        for container in containers:
            if container.get("version_locked") is not True:
                continue

            node = nuke.toNode(container["objectName"])
            container["version_locked"] = False
            imprint(node, {"avalon:version_locked": False})
            node["avalon:version_locked"].setLabel("Version locked")
