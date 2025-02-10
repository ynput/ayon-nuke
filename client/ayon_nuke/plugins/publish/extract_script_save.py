import nuke
import pyblish.api


class ExtractScriptSave(pyblish.api.InstancePlugin):
    """Save current Nuke workfile script"""
    label = 'Script Save'
    order = pyblish.api.ExtractorOrder - 0.1
    hosts = ["nuke"]

    settings_category = "nuke"

    def process(self, instance):

        self.log.debug('Saving current script')
        nuke.scriptSave()

        if "stagingDir" in instance.data.keys():
            self.log.debug(f"StagingDir: {instance.data.get('stagingDir')}")
        else:
            self.log.debug("staging dir not in instance data!")
        self.log.debug("\n" + '\n'.join([f"    {k}: {v}" for k, v in instance.data.items()]))
