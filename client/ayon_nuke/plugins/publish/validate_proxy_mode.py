import pyblish
import nuke
from ayon_core.pipeline import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin,
)


class FixProxyMode(pyblish.api.Action):
    """
    Togger off proxy switch OFF
    """

    label = "Repair"
    icon = "wrench"
    on = "failed"

    def process(self, context, plugin):
        rootNode = nuke.root()
        rootNode["proxy"].setValue(False)


class ValidateProxyMode(
    OptionalPyblishPluginMixin,
    pyblish.api.ContextPlugin,
):
    """Validate active proxy mode"""

    order = pyblish.api.ValidatorOrder
    optional = False
    label = "Validate Proxy Mode"
    hosts = ["nuke"]
    actions = [FixProxyMode]

    settings_category = "nuke"

    def process(self, context):
        if not self.is_active(context.data):
            return

        rootNode = nuke.root()
        isProxy = rootNode["proxy"].value()

        if isProxy:
            raise PublishXmlValidationError(
                self, "Proxy mode should be toggled OFF"
            )
