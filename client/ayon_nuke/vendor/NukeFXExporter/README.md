NukeFXSExporter
===============
Nuke .fxs (Silhouette Shape format) exporter.

This script will export Nuke shapes to a Silhouette Roto and Paint shape format .fxs file.    
That allows a Mocha to Silhouette shape export using Nuke.

Youtube video:    
<a href="http://www.youtube.com/watch?feature=player_embedded&v=Xn9oegH8umo" target="_blank"><img src="http://img.youtube.com/vi/Xn9oegH8umo/mqdefault.jpg"
alt="Click to Watch the video" width="240" height="135" border="10" /></a>



    
If you like it, use it frequently, or want to support further development
please consider a small donation to the author.     
https://www.paypal.me/mborgo

You can find my contact info at http://boundaryvfx.com/research_and_development/

### SUPPORTED FEATURES: ###

**Version 2.0: initial release Aug 5th 2013**

This version introduces Shapes and Layers transforms exports: meaning "tracking data (point/cpin)" export
and avoiding baking the keyframes everywhere.

* Shape Position/Animation
* Shape Opacity (Linear/Constant keyframes)
* Shape Motion Blur
* Shape Overlay Color
* Shape Blending Modes
* Shape Inverted attribute
* Shape Open/Closed
* Delete repeated baked keyframes when possible
* Layer/Shape Transforms (all transforms, including "extra matrix")
* Layer nesting

#### COMPATIBILITY ####

Nukev7 and up

#### KNOW LIMITATIONS ####
* Nuke animation curves are more complex than Silhouette ones, that will result in more keyframes depending on the keyframe interpolation
* B-spline Tension not supported yet
* Feather not supported
* Rectangles are exported incorrectly (swapped tangents). 
  > Workaround: smooth and cusp the points back, it will fix the tangents.
* For heavy scenes, the script might take a while to give the task feedback, be patient.

#### USAGE ####

Select the Roto or Rotopaint node and run the script from the Script Editor.
You can set a the default folder/file path on init.py or menu.py with the code below:   

    os.environ['FXSEXPORTPATH'] = '/path/to/your/fxsfile.fxs'
    
Optionally you can use the provided "menu.py" file to get a Toolbar item with the script.


#### BUG REPORT ####
Send me (contact info at http://boundaryvfx.com/tools) the Nuke Console error message and your Roto/Rotopaint node for troubleshooting.


#### Thanks ####
Kudos to the Silhouette team: Paul Miller and Perry Kivolowitz that helped me with important info.

#### Licensing ####
This script is made available under a BSD Style license that is included with the package.
