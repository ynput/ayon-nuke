import os
import re
import xml.etree.ElementTree as xmlt
import pyblish.api

class IntegrateOpenclip(pyblish.api.InstancePlugin):
    """Automatically create openclips for all clippable representations with a publish path."""

    label = "Integrate Openclip"
    order = pyblish.api.IntegratorOrder + 0.51
    families = ['render', 'plate','prerender']
    hosts = ['nuke', 'standalonepublisher', 'traypublisher', 'shell']
    targets = ['local', 'deadline', 'a_frames_farm', 'farm']

    template = """<?xml version="1.0"?>
<clip type="clip" version="6">
    <handler>
        <name>MIO Clip</name>
        <version>2</version>
        <options type="dict">
            <ScanPattern type="string"></ScanPattern>
        </options>
    </handler>
</clip>"""

    def process(self, instance):
        supported_exts = {'jpg', 'exr', 'hdr', 'raw', 'dpx', 'png', 'jpeg', 'mov', 'mp4', 'tiff', 'tga'}
        clippable_reps = [
            rep for rep in instance.data.get("representations", [])
            if rep.get('ext') in supported_exts and 'published_path' in rep
        ]
        if len(clippable_reps) < 1:
            self.log.warning('No media to make openclip from')
            return
        workf = os.path.join(instance.data['publishDir'],'..')
        os.makedirs(workf, exist_ok=True)
        posix_base = workf.replace('P:\\', '/Volumes/production/').replace('D:\\', '/Volumes/production/').replace('V:\\', '/Volumes/vfxprod/').replace('\\', '/')

        for rep in clippable_reps:
            if 'published_path' not in rep.keys() or rep['ext'] not in supported_exts:
                continue
            ext = rep['ext']
            pattern = rep['published_path']
            patternNoExt = os.path.splitext(pattern)[0]
            patternStripped = re.sub(r'[0-9]+$', '{frame}', patternNoExt.replace('\\', '/').replace('P:', '/Volumes/production').replace('D:', '/Volumes/production').replace('V:\\', '/Volumes/vfxprod'))

            regex = re.compile('(?<=[/._])v\d{3}(?=[/._])')
            versions = regex.sub('v{version}', patternStripped) if ext not in ['mov', 'mp4'] else patternStripped

            clip_path_win = os.path.join(workf, f"{instance.data['folderPath'].replace('/','_')}_{instance.data['name']}_{rep['ext']}.clip")
            tree = xmlt.fromstring(self.template)
            tree.find('.//ScanPattern').text = f"{versions}.{ext}"

            with open(clip_path_win, 'wb') as fout:
                fout.write(xmlt.tostring(tree))
            if not os.path.exists(clip_path_win):
                raise Exception(f'Clip file generation failed for {clip_path_win}')
