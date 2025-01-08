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


        source_path = Path(instance.data["path"])
        source_dir = source_path.parent
        publish_format = source_path.suffix[1:]

        # self.log.info(instance.data)
        # self.log.info(instance.data.keys())

        
        reps = instance.data["published_representations"].values()



        for rep in [r['representation'] for r in reps]:

            if not rep['name'] == publish_format:
                continue

            source_script_path = self.get_script_path(source_dir)

            if source_script_path == None:
                self.log.warn("Source script not found - using current script")
                source_script_path =  current_file = os.path.normpath(nuke.root().name())
                # self.log.info(f"source_script_path: {source_script_path}")
                # return
            
                # the below code causes nuke to crash

                # self.log.warn("Source script not found - saving current script")
                # nuke.scriptSaveToTemp(source_script_path)

            target_path = Path(rep["attrib"]["path"])
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
                self.log.info(f"Script copy succeeded")


    def get_script_path(self, path):

        nuke_scripts = [file for file in path.iterdir() if file.suffix == '.nk']
        if len(nuke_scripts) == 0:
            return None
        
        # for script in nuke_scripts:
        #     self.log.info(script)

        newest_script = max(nuke_scripts, key=os.path.getmtime)

        return newest_script


        # self.log.info("------")
        # for key in instance.data.keys():
        #     self.log.info(key)

        # self.log.info("------ representations -------")

        # for rep in instance.data.get("representations", []):
        #     self.log.info(rep.keys()) 

        self.log.info(instance.data["path"])


        

        # supported_exts = {'jpg', 'exr', 'hdr', 'raw', 'dpx', 'png', 'jpeg', 'mov', 'mp4', 'tiff', 'tga'}
        # clippable_reps = [
        #     rep for rep in instance.data.get("representations", [])
        #     if rep.get('ext') in supported_exts and 'published_path' in rep
        # ]
        # if len(clippable_reps) < 1:
        #     self.log.warning('No media to make openclip from')
        #     return
        # workf = os.path.join(instance.data['publishDir'],'..')
        # os.makedirs(workf, exist_ok=True)
        # posix_base = workf.replace('P:\\', '/Volumes/production/').replace('D:\\', '/Volumes/production/').replace('V:\\', '/Volumes/vfxprod/').replace('\\', '/')

        # for rep in clippable_reps:
        #     if 'published_path' not in rep.keys() or rep['ext'] not in supported_exts:
        #         continue
        #     ext = rep['ext']
        #     pattern = rep['published_path']
        #     patternNoExt = os.path.splitext(pattern)[0]
        #     patternStripped = re.sub(r'[0-9]+$', '{frame}', patternNoExt.replace('\\', '/').replace('P:', '/Volumes/production').replace('D:', '/Volumes/production').replace('V:\\', '/Volumes/vfxprod'))

        #     regex = re.compile('(?<=[/._])v\d{3}(?=[/._])')
        #     versions = regex.sub('v{version}', patternStripped) if ext not in ['mov', 'mp4'] else patternStripped

        #     clip_path_win = os.path.join(workf, f"{instance.data['name']}_{rep['ext']}.clip")
        #     tree = xmlt.fromstring(self.template)
        #     tree.find('.//ScanPattern').text = f"{versions}.{ext}"

        #     with open(clip_path_win, 'wb') as fout:
        #         fout.write(xmlt.tostring(tree))
        #     if not os.path.exists(clip_path_win):
        #         raise Exception(f'Clip file generation failed for {clip_path_win}')


