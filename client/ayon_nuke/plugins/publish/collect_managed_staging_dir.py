"""
Requires:
    anatomy


Provides:
    instance.data     -> stagingDir (folder path)
                      -> stagingDir_persistent (bool)
"""

import pyblish.api

from ayon_core.pipeline.publish import get_instance_staging_dir


class CollectManagedStagingDir(pyblish.api.InstancePlugin):

    """
    HORNET
    Overriding the one from Core to fix the issue that the project configs
    are resulting in a staging dir on the local C: drive that cannot be accessed by the farm.
    
    I have not been able to find a project config solution to this yet.
    
    """




    """Apply matching Staging Dir profile to a instance.

    Apply Staging dir via profiles could be useful in specific use cases
    where is desirable to have temporary renders in specific,
    persistent folders, could be on disks optimized for speed for example.

    It is studio's responsibility to clean up obsolete folders with data.

    Location of the folder is configured in:
        `ayon+anatomy://_/templates/staging`.

    Which family/task type/subset is applicable is configured in:
        `ayon+settings://core/tools/publish/custom_staging_dir_profiles`
    """

    


    label = "Collect Managed Staging Directory"
    order = pyblish.api.CollectorOrder + 0.4990

    def process(self, instance):
        """ Collect the staging data and stores it to the instance.

        Args:
            instance (object): The instance to inspect.
        """
        # # self.log.debug(f"{get_instance_staging_dir(instance, self.log)}")

        #hornet
        self.log.warning(
            "This returns a staging dir on the local C: drive that cannot be accessed by the farm."
        )
        self.log.warning(
            "The issue is related to lib.get_staging_dir_info() failing to find the appropriate template, but so far I have not been able to set the project settings correctly in Ayon."
        )
        self.log.warning(
            "Bypassing this plugin, which causes a later step to fallback on a valid staging dir."
        )
        return



        if "stagingDir" in instance.data.keys():
            self.log.debug(f"StagingDir was already in instance data: {instance.data.get('stagingDir')}")
        else:
            self.log.debug("staging dir not in instance data!")


        staging_dir_path = get_instance_staging_dir(instance, self.log)
        persistance = instance.data.get("stagingDir_persistent", False)

        self.log.info((
            f"Instance staging dir was set to `{staging_dir_path}` "
            f"and persistence is set to `{persistance}`"
        ))
