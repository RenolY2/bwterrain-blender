# Battalion Wars Terrain Blender Plugin
A plugin to edit Battalion Wars 1 terrain.
Battalion Wars 2 support planned in the future.

# Requirements:
Blender 4.5 or newer recommended. 

# Download
Check https://github.com/RenolY2/bwterrain-blender/releases for the latest releases!

# How to Install
In Blender, open Edit -> Preferences, and choose the Add-ons tab on the left if it isn't selected already. Press the little arrow in the upper right and choose "Install from Disk". Select the plugin's zip file to install it.

# Basic Usage
Under File->Import->Battalion Wars Terrain (.out) you can import BW terrain.
The terrain will be imported in multiple pieces (because Blender struggles to edit meshes with too many vertices), each of which can be edited separately, deleted, or duplicated.
The majority of the BW Terrain Tools are in a BW Terrain tab in the side bar that can be pulled out by pulling on the arrow in the top right corner of the main 3D view, under Options.
All the tools come with tooltips if you hover your mouse over the button. The tools provide important functionality that helps work with BW terrain in Blender or provide shortcuts to more quickly edit specific parts of the terrain.

Terrain editing is based on vertex paint and vertex weight editing. There are two color groups (Color, Blend) and three weight groups (Height, Delete, Material).
Color: The color of a point. Grey roughly corresponds to a neutral color, white is very bright. and black is completely dark.
Blend: Add or remove alpha to change the blending. Remove alpha to make main texture more visible, add alpha to make detail texture more visible.
Height: A weight of 0.1 corresponds to 51.2 units of height.
Delete: A weight of 1.0 deletes a part of the terrain, 0.0 makes it appear.
Material: The weight value multiplied by 100 corresponds to the number of the material to be painted with. Example: Weight of 0.01 paints with the material number 1.

A material has a main and a detail texture. Based on that you need to correctly choose which materials to paint for smooth transitions. Pro tip: A lot of different materials using the same main texture can be blended together for smooth transitions. 

Please do not delete or add vertices or use other mesh operators that in some way modify the terrain geometry, or rotate the terrain objects.. This will likely corrupt the terrain visually and in the terrain data. You can expand the level by duplicating the terrain chunks, but avoid going over the level boundary of -2048 to 2048, and keep the terrain chunk positions at a multiple of 64.
Please note: If you add new textures, exporting terrain will also modify the level's .res and .xml file, so when editing the terrain only load the level in the BW Level Editor after you edited the terrain, or reload the level without saving first 

Watch https://www.youtube.com/watch?v=0JXCK-H6Fxc for a walkthrough of most of the editor's functionality.


<img width="1908" height="1040" alt="image" src="https://github.com/user-attachments/assets/203d8927-9bc7-431c-b790-778e0414b9d8" />


