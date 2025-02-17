import os
import re
import xml.etree.ElementTree as xmlt
import pyblish.api
import shutil
import nuke
from pathlib import Path

class IntegrateSubmissionWorkfile(pyblish.api.InstancePlugin):
    """Automatically create openclips for all clippable representations with a publish path."""

    label = "Integrate Submission Workfile"
    order = pyblish.api.IntegratorOrder + 0.51
    families = ['render', 'plate','prerender']
    hosts = ['nuke']
    targets = ['local', 'deadline', 'a_frames_farm', 'farm']

    def process(self, instance):

        self.log.info("Integrating submission workfile")

        source_path = Path(instance.data["path"])
        source_dir = source_path.parent
        publish_format = source_path.suffix[1:]


        target_path = get_target_path(instance)

        self.log.info(f"Target path: {target_path}")

        # reps = instance.data["published_representations"].values()

        # reps = instance.data.get("representations", [])

        # for rep in [r.get('representation', None) for r in reps]:

        #     if not rep:
        #         continue

        #     if not rep['name'] == publish_format:
        #         continue

        #     self.log.info(f"Processing {rep['name']}")
        
        # Save the latest script in the source dir along with the publish
        




        source_script_path = self.get_script_path(source_dir)

        self.log.info(f"source script path: {source_script_path}")

        if source_script_path is None:
            self.log.warn("Source script not found - using current script")
            source_script_path = os.path.normpath(nuke.root().name())

        # target_path = Path(rep["attrib"]["path"])
        target_dir = target_path.parent
        target_scrtipt_file = str(target_path.stem).split(".")[0] + ".nk"
        target_script_path = target_dir / target_scrtipt_file
        
        self.log.info(f"source script path: {source_script_path}") 
        self.log.info(f"target script file: {target_script_path}") 

        try:
            shutil.copy2(source_script_path, target_script_path)
        except shutil.Error as e:
            self.log.error(f'Copy error: {e}')
        except OSError as e:
            self(f'OS error: {e}')

        if os.path.exists(target_script_path):
            self.log.info("Script copy succeeded")


    def get_script_path(self, path):

        path = Path(path)/"scripts"

        if not path.exists():
            return None

        nuke_scripts = [file for file in path.iterdir() if file.suffix == '.nk']
        if len(nuke_scripts) == 0:
            return None

        newest_script = max(nuke_scripts, key=os.path.getmtime)

        return newest_script


def get_target_path(instance):
    """Get the target publish path without needing representation data."""
    
    # Get the publish directory from instance
    publish_dir = instance.data.get('publishDir')
    
    # Get the filename components
    folder_name = instance.data['folder']['name']
    product_name = instance.data['product']['name']
    version = f"v{str(instance.data['version']).zfill(3)}"
    extension = instance.data.get('ext', 'exr')
    
    # Construct filename
    # Format: {folder_name}_{product_name}_{version}.{frame}.{ext}
    filename = f"{folder_name}_{product_name}_{version}.####.{extension}"
    
    # Join with publish directory
    target_path = os.path.join(publish_dir, filename)
    
    return Path(target_path)