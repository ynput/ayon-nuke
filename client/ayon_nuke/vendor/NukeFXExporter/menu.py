import nuke, os
nuke.tprint('Loading NukeFXSExporter.py')
try:
    from NukeFXSExporter import *
except:
    pass

#===============================================================================
# BVFX ToolBar Menu definitions
#===============================================================================
toolbar = nuke.menu("Nodes")
bvfxt = toolbar.addMenu("BoundaryVFX Tools", "BoundaryVFX.png")
bvfxt.addCommand('Silhouette FXS exporter', 'silhouetteFxsExporter()', icon='BoundaryVFX.png')


#===============================================================================
# Uncomment the code below to enable automatic file saving to a predefined path/file
#===============================================================================
#os.environ['FXSEXPORTPATH'] = '/path/to/your/fxsfile.fxs'