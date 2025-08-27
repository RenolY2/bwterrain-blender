import bpy
import bmesh 
import os 
print(os.getcwd())
import importlib


def rename():
    for obj in bpy.context.selected_objects:
        if obj.get("BattalionWars", False):
            for i, mat in enumerate(obj.material_slots[1:]):
                name1 = mat.material.node_tree.nodes["texturemain"].image.name.split(".")[0]
                name2 = mat.material.node_tree.nodes["texturedetail"].image.name.split(".")[0]
                
                mat_name = f"Mat{i:02}_{name1.lower()}_{name2.lower()}"
                mat.material.name = mat_name


def sew_terrain(selected_only, visible_only):
    if selected_only:
        objects = bpy.context.selected_objects
    else:
        objects = bpy.context.scene.objects.values()
    corner_heights = {}

    for obj in objects:
        if obj.get("BattalionWars", False) and (not visible_only or obj.visible_get()):
            vtx_count = len(obj.data.vertices)
            size = int(vtx_count**0.5)
            assert vtx_count**0.5 % 1 == 0, "needs to be a square number"
            assert size % 4 == 0, "needs to be a multiple of 4"
            
            base_x = int((obj.location[0] + 2048))//4
            base_y = int((obj.location[1] + 2048))//4
            
            print(obj.name, base_x, base_y)
            get_weight = obj.vertex_groups["Height"].weight
            
            for ix in range(size):
                x = base_x + ix - (base_x + ix)//4
                
                for iy in range(size):
                    y = base_y + iy - (base_y + iy)//4
                    
                    if 0 <= base_x + ix < 1024 and 0 <= base_y + iy < 1024:
                        if (x,y) not in corner_heights:
                            corner_heights[(x,y)] = []
                      
                        try:
                            weight = get_weight(iy + ix*size)
                        except RuntimeError:
                            pass 
                        else:
                            corner_heights[(x,y)].append(weight)



    for obj in objects:
        if obj.get("BattalionWars", False) and (not visible_only or obj.visible_get()):
            vtx_count = len(obj.data.vertices)
            size = int(vtx_count**0.5)
            assert vtx_count**0.5 % 1 == 0, "needs to be a square number"
            assert size % 4 == 0, "needs to be a multiple of 4"
            
            base_x = int((obj.location[0] + 2048))//4
            base_y = int((obj.location[1] + 2048))//4
            
            print(obj.name, base_x, base_y)
            add_weight = obj.vertex_groups["Height"].add
            
            for ix in range(size):
                x = base_x + ix - (base_x + ix)//4
                
                for iy in range(size):
                    y = base_y + iy - (base_y + iy)//4
                    
                    if 0 <= base_x + ix < 1024 and 0 <= base_y + iy < 1024:
                        if (x,y) in corner_heights and len(corner_heights[(x,y)]) > 1:
                            avg = sum(corner_heights[(x,y)])/len(corner_heights[(x,y)])
                            add_weight([iy + ix*size], avg, "REPLACE")

def reset_uv_selected_objects(main_uv=True, detail_uv=True):
    for obj in bpy.context.selected_objects:
        if obj.get("BattalionWars", False):
            vtx_count = len(obj.data.vertices)
            size = int(vtx_count**0.5)
            assert vtx_count**0.5 % 1 == 0, "needs to be a square number"
            assert size % 4 == 0, "needs to be a multiple of 4"
            
            base_x = int((obj.location[0] + 2048))//4
            base_y = int((obj.location[1] + 2048))//4

            detail = obj.data.uv_layers['UVDetail']
            main = obj.data.uv_layers['UVMain']
            
            for face in obj.data.polygons:
                for vtx_i, loop_i in zip(face.vertices, face.loop_indices):
                    local_x = vtx_i//size
                    local_y = vtx_i%size
                    
                    x = base_x + local_x 
                    y = base_y + local_y
                    
                    cx = y // 16 
                    cy = x // 16
                    
                    if 0 <= x < 1024 and 0 <= y < 1024:
                        tile_x = x % 16 
                        tile_y = y % 16
                        
                        in_tile_x = x % 4 
                        in_tile_y = y % 4
     
                        if main_uv:
                            main.data[loop_i].uv = (in_tile_x/3.0, in_tile_y/3.0)
                        if detail_uv:
                            detail.data[loop_i].uv = (in_tile_x/3.0, in_tile_y/3.0)