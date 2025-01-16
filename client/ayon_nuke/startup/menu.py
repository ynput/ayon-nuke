from ayon_core.pipeline import install_host
from ayon_nuke.api import NukeHost
from hornet_deadline_utils import deadlineNetworkSubmit, save_script_with_render
import read_node_generators
host = NukeHost()
install_host(host)
import nuke
import os
import json
from pathlib import Path

from ayon_core.lib import Logger
from ayon_nuke import api
from ayon_nuke.api.lib import (
    on_script_load,
    check_inventory_versions,
    WorkfileSettings,
    dirmap_file_name_filter,
    add_scripts_gizmo,
    create_write_node
)
from ayon_core.settings import get_project_settings
log = Logger.get_logger(__name__)
# dict mapping extension to list of exposed parameters from write node to top level group node
knobMatrix = { 'exr': ['autocrop', 'datatype', 'heroview', 'metadata', 'interleave'],
                'png': ['datatype'],
                'dpx': ['datatype'],
                'tiff': ['datatype', 'compression'],
                'jpeg': []
}



universalKnobs = ['colorspace', 'views']

knobMatrix = {key: universalKnobs + value for key, value in knobMatrix.items()}
presets = {
    'exr' : [ ("colorspace", 'ACES - ACEScg'), ('channels', 'all'), ('datatype', '16 bit half') ],
    'png' : [ ("colorspace", 'Output - Rec.709'), ('channels', 'rgba'), ('datatype','16 bit') ],
    'dpx' : [ ("colorspace", 'Output - Rec.709'), ('channels', 'rgb'), ('datatype','10 bit'), ('big endian', True) ],
    'jpeg' : [ ("colorspace", 'Output - sRGB'), ('channels', 'rgb') ]
           }
def apply_format_presets():
    node = nuke.thisNode()
    knob = nuke.thisKnob()
    if knob.name() == 'file_type':
        if knob.value() in presets.keys():
            for preset in presets[knob.value()]:
                if node.knob(preset[0]):
                    node.knob(preset[0]).setValue(preset[1])
# Hornet- helper to switch file extension to filetype
def writes_ver_sync():
    ''' Callback synchronizing version of publishable write nodes
    '''
    try:
        print('Hornet- syncing version to write nodes')
        #rootVersion = pype.get_version_from_path(nuke.root().name())
        pattern = re.compile(r"[\._]v([0-9]+)", re.IGNORECASE)
        rootVersion = pattern.findall(nuke.root().name())[0]
        padding = len(rootVersion)
        new_version = "v" + str("{" + ":0>{}".format(padding) + "}").format(
            int(rootVersion)
        )
        print("new_version: {}".format(new_version))
    except Exception as e:
        print(e)
        return
    groupnodes = [node.nodes() for node in nuke.allNodes() if node.Class() == 'Group']
    allnodes = [node for group in groupnodes for node in group] + nuke.allNodes()
    for each in allnodes:
        if each.Class() == 'Write':
            # check if the node is avalon tracked
            if each.name().startswith('inside_'):
                avalonNode = nuke.toNode(each.name().replace('inside_',''))
            else:
                avalonNode = each
            if "AvalonTab" not in avalonNode.knobs():
                print("tab failure")
                continue

            avalon_knob_data = avalon.nuke.get_avalon_knob_data(
                avalonNode, ['avalon:', 'ak:'])
            try:
                if avalon_knob_data['families'] not in ["render", "write"]:
                    print("families fail")
                    log.debug(avalon_knob_data['families'])
                    continue

                node_file = each['file'].value()

                #node_version = "v" + pype.get_version_from_path(node_file)
                node_version = 'v' + pattern.findall(node_file)[0]

                log.debug("node_version: {}".format(node_version))

                node_new_file = node_file.replace(node_version, new_version)
                each['file'].setValue(node_new_file)
                #H: don't need empty folders if work file isn't rendered later
                #if not os.path.isdir(os.path.dirname(node_new_file)):
                #    log.warning("Path does not exist! I am creating it.")
                #    os.makedirs(os.path.dirname(node_new_file), 0o766)
            except Exception as e:
                print(e)
                log.warning(
                    "Write node: `{}` has no version in path: {}".format(
                        each.name(), e))


def switchExtension():
    nde = nuke.thisNode()
    knb = nuke.thisKnob()
    if knb == nde.knob('file_type'):
        filek = nde.knob('file')
        old = filek.value()
        pre,ext = os.path.splitext(old)
        filek.setValue(pre + '.' + knb.value())

def embedOptions():

    nde = nuke.thisNode()
    knb = nuke.thisKnob()
    # log.info(' knob of type' + str(knb.Class()))
    htab = nuke.Tab_Knob('htab','Hornet')
    htab.setName('htab')
    if knb == nde.knob('file_type'):
        group = nuke.toNode('.'.join(['root'] + nde.fullName().split('.')[:-1]))
        ftype = knb.value()
    else:
        return
    if ftype not in knobMatrix.keys():
        return
    for knb in group.allKnobs():
        try:
            #never clear or touch the invisible string knob that contains the pipeline JSON data
            if knb.name() != api.INSTANCE_DATA_KNOB:
                group.removeKnob(knb)
        except:
            continue
    beginGroup = nuke.Tab_Knob('beginoutput', 'Output', nuke.TABBEGINGROUP)
    group.addKnob(beginGroup)

    if 'file' not in group.knobs().keys():
        fle = nuke.Multiline_Eval_String_Knob('File output')
        fle.setText(nde.knob('file').value())
        group.addKnob(fle)
        link = nuke.Link_Knob('channels')
        link.makeLink(nde.name(), 'channels')
        link.setName('channels')
        group.addKnob(link)
        if 'file_type' not in group.knobs().keys():
            link = nuke.Link_Knob('file_type')
            link.makeLink(nde.name(), 'file_type')
            link.setName('file_type')
            link.setFlag(0x1000)
            group.addKnob(link)
        for kname in knobMatrix[ftype]:
            link = nuke.Link_Knob(kname)
            link.makeLink(nde.name(), kname)
            link.setName(kname)
            link.setFlag(0x1000)
            group.addKnob(link)
    log.info("links made")
    renderFirst = nuke.Link_Knob('first')
    renderFirst.makeLink(nde.name(), 'first')
    renderFirst.setName('Render Start')

    renderLast = nuke.Link_Knob('last')
    renderLast.makeLink(nde.name(), 'last')
    renderLast.setName('Render End')

    publishFirst = nuke.Int_Knob('publishFirst', 'Publish Start')
    publishLast = nuke.Int_Knob('publishLast', 'Publish End')
    usePublishRange = nuke.Boolean_Knob('usePublishRange', 'My Publish Range is different from my render range')
    usePublishRange.setFlag(nuke.STARTLINE)
    nde.knob('first').setValue(nuke.root().firstFrame())
    nde.knob('last').setValue(nuke.root().lastFrame())
    publishFirst.setValue(nuke.root().firstFrame())
    publishLast.setValue(nuke.root().lastFrame())
    publishFirst.setEnabled(False)
    publishLast.setEnabled(False)
    usePublishRange.setValue(False)

    endGroup = nuke.Tab_Knob('endoutput', None, nuke.TABENDGROUP)
    group.addKnob(endGroup)
    beginGroup = nuke.Tab_Knob('beginpipeline', 'Rendering and Pipeline', nuke.TABBEGINGROUP)
    group.addKnob(beginGroup)

    publishFirst.clearFlag(nuke.STARTLINE)
    group.addKnob(renderFirst)

    group.addKnob(publishFirst)
    publishLast.clearFlag(nuke.STARTLINE)
    group.addKnob(renderLast)
    group.addKnob(publishLast)
    group.addKnob(usePublishRange)
    sub = nuke.PyScript_Knob('submit', 'Submit to Deadline', "deadlineNetworkSubmit()")
    sub.setFlag(nuke.STARTLINE)
    clr = nuke.PyScript_Knob('clear', 'Clear Temp Outputs', "import os;fpath = os.path.dirname(nuke.thisNode().knob('File output').value());[os.remove(os.path.join(fpath, f)) for f in os.listdir(fpath)]")
    publish_button = nuke.PyScript_Knob('publish', 'Publish', "from ayon_core.tools.utils import host_tools;host_tools.show_publisher(tab='Publish')")
    readfrom_src = "import read_node_generators;read_node_generators.write_to_read(nuke.thisNode(), allow_relative=False)"
    readfrom = nuke.PyScript_Knob('readfrom', 'Read From Rendered', readfrom_src)
    # link = nuke.Link_Knob('render')
    # link.makeLink(nde.name(), 'Render')
    # link.setName('Render Local')
    # link.setFlag(nuke.STARTLINE)
    render_local_button = nuke.PyScript_Knob('renderlocal', 
                                             'Render Local', 
                                             "nuke.toNode(f'inside_{nuke.thisNode().name()}').knob('Render').execute();save_script_with_render(nuke.thisNode()['File output'].getValue())")    
    group.addKnob(render_local_button)
    # group.addKnob(link)

    div = nuke.Text_Knob('div','','')
    deadlinediv = nuke.Text_Knob('deadlinediv','Deadline','')
    deadlinePriority = nuke.Int_Knob('deadlinePriority', 'Priority')
    deadlineChunkSize = nuke.Int_Knob('deadlineChunkSize', 'Chunk Size')
    concurrentTasks = nuke.Int_Knob('concurrentTasks', 'Concurrent Tasks')
    deadlinePool = nuke.String_Knob('deadlinePool', 'Pool')
    deadlineGroup = nuke.String_Knob('deadlineGroup', 'Group')

    read_from_publish_button = nuke.PyScript_Knob('readfrompublish', 'Read From Publish', "read_node_generators.read_from_publish(nuke.thisNode())")
    
    deadlineChunkSize.setValue(1)
    concurrentTasks.setValue(1)
    deadlinePool.setValue('local')
    deadlineGroup.setValue('nuke')
    deadlinePriority.setValue(90)
    
    deadlinePriority.setFlag(nuke.STARTLINE)
    deadlineChunkSize.clearFlag(nuke.STARTLINE)  # Don't start a new line
    concurrentTasks.clearFlag(nuke.STARTLINE)
    
    group.addKnob(readfrom)
    group.addKnob(clr)
    group.addKnob(deadlinediv)
    
    group.addKnob(deadlinePriority)
    group.addKnob(deadlineChunkSize)
    group.addKnob(concurrentTasks)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       
    group.addKnob(deadlinePool)
    group.addKnob(deadlineGroup)
    group.addKnob(sub)
    group.addKnob(div)
    group.addKnob(publish_button)
    group.addKnob(read_from_publish_button)
    tempwarn = nuke.Text_Knob('tempwarn', '', '- all rendered files are TEMPORARY and WILL BE OVERWRITTEN unless published ')
    group.addKnob(tempwarn)

    endGroup = nuke.Tab_Knob('endpipeline', None, nuke.TABENDGROUP)
    group.addKnob(endGroup)


def quick_write_node(family='render'):

    variant = nuke.getInput('Variant for Quick Write Node','Main').title()
    _quick_write_node(variant, family)


def _quick_write_node(variant, family='render'):

    variant = variant.title()

    print("quick write node")
    nuke.tprint('quick write node')

    if '/' in os.environ['AYON_FOLDER_PATH']:
        ayon_asset_name = os.environ['AYON_FOLDER_PATH'].split('/')[-1]
    else:
        ayon_asset_name = os.environ['AYON_FOLDER_PATH']

    if any(var is None or var == '' for var in [os.environ['AYON_TASK_NAME'],ayon_asset_name]):
        nuke.alert("missing AYON_TASK_NAME and AYON_FOLDER_PATH, can't make quick write")

    # variant = nuke.getInput('Variant for Quick Write Node','Main').title()
    variant = '_' + variant if variant[0] != '_' else variant
    if variant == '_' or variant == None or variant == '':
        nuke.message('No Variant Specified, will not create Write Node')
        return
    for nde in nuke.allNodes('Write'):
        if nde.knob('name').value() == family + os.environ['AYON_TASK_NAME'] + variant:
            nuke.message('Write Node already exists')
            return
    data = {'subset':family + os.environ['AYON_TASK_NAME'] + variant,'variant': variant,
            'id':'pyblish.avalon.instance','creator': f'create_write_{family}','creator_identifier': f'create_write_{family}',
            'folderPath': ayon_asset_name,'task': os.environ['AYON_TASK_NAME'],
            'productType': family,
            'task': {'name': os.environ['AYON_TASK_NAME']},
            'productName': family + os.environ['AYON_TASK_NAME'] + variant,
            'hierarchy': '/'.join(os.environ['AYON_FOLDER_PATH'].split('/')[:-1]),
            'folder': {'name': os.environ['AYON_FOLDER_PATH'].split('/')[-1]},
            'fpath_template':"{work}/renders/nuke/{subset}/{subset}.{frame}.{ext}"}
    qnode = create_write_node(family + os.environ['AYON_TASK_NAME'] + variant,
                              data,
                              prerender=True if family == 'prerender' else False)
    qnode = nuke.toNode(family + os.environ['AYON_TASK_NAME'] + variant)
    print(f'Created Write Node: {qnode.name()}')
    api.set_node_data(qnode,api.INSTANCE_DATA_KNOB,data)
    instance_data = json.loads(qnode.knob(api.INSTANCE_DATA_KNOB).value()[7:])
    instance_data.pop('version',None)
    instance_data['task'] = os.environ['AYON_TASK_NAME']
    instance_data['creator_attributes'] = {'render_taget': 'frames_farm', 'review': True}
    instance_data['publish_attributes'] = {"CollectFramesFixDef": {"frames_to_fix": "", "rewrite_version": False},
                                                                 "ValidateCorrectAssetContext": {"active": True},
                                                                 "NukeSubmitDeadline": {"priority": 90, "chunk": 1, "concurrency": 1, "use_gpu": True, "suspend_publish": False, "workfile_dependency": True, "use_published_workfile": True}}
    qnode.knob(api.INSTANCE_DATA_KNOB).setValue("JSON:::" + json.dumps(instance_data))
    if family == 'prerender':
        qnode.knob('tile_color').setValue(2880113407)
    with qnode.begin():
        inside_write = nuke.toNode('inside_'+ family + os.environ['AYON_TASK_NAME'] + variant.title())
        inside_write.knob('file_type').setValue('exr')

    

    return qnode
def enable_disable_frame_range():
    nde = nuke.thisNode()
    knb = nuke.thisKnob()
    if not nde.knob('use_limit') or not knb.name() == 'use_limit':
        return
    group = nuke.toNode('.'.join(['root'] + nde.fullName().split('.')[:-1]))
    enable = nde.knob('use_limit').value()
    group.knobs()['first'].setEnabled(enable)
    group.knobs()['last'].setEnabled(enable)

def submit_selected_write():
    for nde in nuke.selectedNodes():
        if nde.Class() == 'Write':
            submit_write(nde)
def enable_publish_range():
    nde = nuke.thisNode()
    kb = nuke.thisKnob()
    if not kb == nde.knob('usePublishRange'):
        return
    if kb.value():
        nde.knob('publishFirst').setEnabled(True)
        nde.knob('publishLast').setEnabled(True)
    else:
        nde.knob('publishFirst').setEnabled(False)
        nde.knob('publishLast').setEnabled(False)



hornet_menu = nuke.menu("Nuke")
m = hornet_menu.addMenu("&Hornet_harding_tinkering")
m.addCommand("&Quick Write Node", "quick_write_node()", "Ctrl+W")
m.addCommand("&Quick PreWrite Node", "quick_write_node(family='prerender')", "Ctrl+Shift+W")
nuke.addKnobChanged(apply_format_presets, nodeClass='Write')
nuke.addKnobChanged(switchExtension, nodeClass='Write')
nuke.addKnobChanged(embedOptions, nodeClass='Write')
nuke.addKnobChanged(enable_publish_range, nodeClass='Group')
nuke.addKnobChanged(enable_disable_frame_range, nodeClass='Write')
nuke.addOnScriptSave(writes_ver_sync)
nuke.addOnScriptLoad(WorkfileSettings().set_colorspace)
nuke.addOnCreate(WorkfileSettings().set_colorspace, nodeClass='Root')

# nuke.addKnobChanged(save_script_on_render, nodeClass='Write')




# View Manager

from view_manager import show as show_view_manager
toolbar = nuke.toolbar("Nodes")
toolbar.addCommand("Alex Dev / View Manager", "show_view_manager()")



# Project Gizmos

PROJECT_NAME = os.environ["AYON_PROJECT_NAME"]

from node_manager import NodeLoader
nodes_toolbar = nuke.toolbar("Nodes")
project_toolbar = nodes_toolbar.addMenu(PROJECT_NAME)

node_loader = NodeLoader()

project_toolbar.addCommand(name="Add Selected Nodes", command="node_loader.add_selected_nodes()")
project_toolbar.addCommand(name="Add Toolset", command="node_loader.add_toolset()")
project_toolbar.addCommand(name="Reload", command="node_loader.populate()")