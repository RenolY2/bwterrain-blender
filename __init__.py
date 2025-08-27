bl_info = {
    "name": "Battalion Wars Terrain Addon",
    "description": "Imports, modifies and exports Battalion Wars 1 terrain (.out)"
    "author": "Yoshi2",
    "version": (1, 1, 0),
    "blender": (4, 5, 0),
    "category": "Import-Export",
    "location": "File>Import/Export;View3D>Side Bar>BW Terrain tab"
    "warning": "Import/Export can take some time (>15 sec)"
}
from . import terrain_addon

import importlib 


def register():
    importlib.reload(terrain_addon)
    terrain_addon.register()

def unregister():
    terrain_addon.unregister()