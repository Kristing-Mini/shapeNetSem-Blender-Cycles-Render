
<!--=## ShapeNetSem Blender Render-->
## ShapeNetSem Blender Render
This is a script to render .obj files with Blender. We can render with Blender render engine and Cycles render engine.  
Tested with Blender 2.79.  
Tested on Linux, Windows.

<!-- Brief Statement-->
##Brief Statement  
We can get RGB images, depth, and mask from this scripts.  
Download the .obj files and .mtl files from ShapeNet website.  
Download the textures.zip from ShapeNet website and extract to the folder where the .obj files and .mtl files are located.  
Run blender.py to use Blender Render engines to render image  
Run cycles.py to use Cycles Render engines to render image.  
We use exr format to save depth infomation. fileSwitch.py provide a way to change the .exr file to .tiff file.  
If you want to run with Blender Render engines, you can use the command  like this    
<code>blender --background --python blender.py -- --views=the number of views you want --obj_files=the path to the obj files --output_folder==the path to the folder you want to save the render output</code>  
For example,  
<code>blender --background --python blender.py -- --views=4 --obj_files=./obj --output_output=render_output</code>  
If you want to render with Cycles Render engines, just change the python file to  cycles.py
Also, you can move the <code>background</code> option. The <code>background</code> options is used for UI-less rendering.






