import os
import re
import xml.etree.ElementTree as xmlt
import pyblish.api
import shutil
from pathlib import Path

class IntegrateSubmissionWorkfile(pyblish.api.InstancePlugin):
    """Automatically create openclips for all clippable representations with a publish path."""

    label = "Integrate Submission Workfile"
    order = pyblish.api.IntegratorOrder + 0.51
    families = ['render', 'plate','prerender']
    hosts = ['nuke']
    targets = ['local', 'deadline', 'a_frames_farm', 'farm']

    def process(self, instance):


        # self.log.info(instance.data)

        # self.log.info(instance.data.keys())

        reps = instance.data["published_representations"].values()

        for rep in reps:

            self.log.info(rep["transfers"])

            from_files = Path(rep["transfers"][0][0])
            from_dir = from_files.parent
            to_files = Path(rep["transfers"][0][1])
            to_dir = Path(to_files.parent)

            self.get_script(from_dir)

            from_script = self.get_script(from_dir)
            to_script = to_dir / Path(str(to_files.stem).split(".")[0] + ".nk")

            self.log.info(from_script)
            # self.log.info(to_files)
            self.log.info(to_script)

            shutil.copy2(from_script, to_script)

    def get_script(self, path):

        nuke_scripts = [file for file in path.iterdir() if file.suffix == '.nk']
        newest_script = max(nuke_scripts, key=os.path.getmtime)

        return newest_script



        # print(instance.data)

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


# [
#     ('P:/projects/ayon/rnd02_ayon/sequences/richk_VDITEST/rkim_010/work/comp/renders/nuke/rendercomp_Main\\rendercomp_Main.0001.exr', 
#   'P:\\projects\\ayon\\rnd02_ayon\\sequences\\richk_VDITEST\\rkim_010\\publish\\render\\rendercomp_Main\\v010\\rnd02_ayon_rkim_010_rendercomp_Main_v010.exr')
# ]