import bpy
import bmesh 
import os 
print(os.getcwd())
import importlib
import timeit

from .bwterrain import texlib
from .bwterrain import bwtex
from .bwxml import SimpleLevelXML

importlib.reload(texlib)

from . import bwterrainnew
importlib.reload(bwterrainnew)
from io import BytesIO

from .bwterrainnew import bw_terrain, binaryreader
from . import bwterrain
importlib.reload(bwterrain)
from .bwterrain.bwarchivelib import BattalionArchive, TextureBW1
importlib.reload(bwtex)
importlib.reload(bwterrainnew)
importlib.reload(bw_terrain)

def open_path(path, mode="rb"):
    if path.endswith(".gz"):
        return gzip.open(path, mode) 
    else:
        return open(path, mode) 
    



def try_get(f, ind):
    try:
        val = f(ind)
    except RuntimeError:
        return None 
    else:
        return val

def value_test(uvval):
    val = int(uvval*4096)
    return 0 <= val <= 2**16-1


def choose_unique_id(num, ids):
        while num in ids:
            num += 7
        
        return num 


def export_terrain(dest, dest_res=None, dest_xml=None, dest_preload_xml=None, selected_only=False, visible_only=True):
    import_textures = dest_res is not None

    if import_textures:
        with open_path(dest_res) as f:
            arc = BattalionArchive.from_file_textures(f)
        
        existing_textures = []
        for tex in arc.textures.textures:
            name = tex.name.upper()
            existing_textures.append(name)
        
        with open(dest_xml, "rb") as f:
            level_xml = SimpleLevelXML(f)
        
        with open(dest_preload_xml, "rb") as f:
            preload_xml = SimpleLevelXML(f)
            
        cummulative_ids = level_xml.ids + preload_xml.ids 
        
        
        
        
    else:
        arc = None 

    with open(dest, "rb") as f:
        br = binaryreader.BinaryReader(f.read())

    terrain = br.read_object(bw_terrain.TerrainFile)
    terrain.clear_chunks()



    all_materials = []
    obj_remap_tables = []
    
    if selected_only:
        objects = bpy.context.selected_objects
    else:
        objects = bpy.context.scene.objects.values()

    for obj in objects:
        if obj.get("BattalionWars", False) and (not visible_only or obj.visible_get()):
            objname = obj.name 
            
            material_slots = obj.material_slots[1:]
            remap_table = []
            for slot in material_slots:
                if slot.material not in all_materials:
                    index = len(all_materials)
                    all_materials.append(slot.material)
                else:
                    index = all_materials.index(slot.material)
                remap_table.append(index)
            
            obj_remap_tables.append((objname, obj, remap_table))


    terrain.materials.materials = []
    bw_textures = {}

    for material in all_materials:
        name1 = material.node_tree.nodes["texturemain"].image.name.split(".")[0]
        name2 = material.node_tree.nodes["texturedetail"].image.name.split(".")[0]
        
        try:
            name1_encoded = bytes(name1, encoding="ascii")
        except UnicodeEncodeError:
            raise RuntimeError(f"Main Texture {name1} in material {material.name} uses non-ASCII characters! Please use latin letters and numbers.")
        
        try:
            name2_encoded = bytes(name2, encoding="ascii")
        except UnicodeEncodeError:
            raise RuntimeError(f"Detail Texture {name2} in material {material.name} uses non-ASCII characters! Please use latin letters and numbers.")
        
        if len(name1) > 16:
            raise RuntimeError(f"Main Texture {name1} in material {material.name} too long! Should be 16 symbols or less.")
        if len(name2) > 16:
            raise RuntimeError(f"Detail Texture {name2} in material {material.name} too long! Should be 16 symbols or less.")
        
        mat = bw_terrain.MapMaterial(
            name1_encoded.lower(), 
            name2_encoded.lower(), 
            material["Value 1"],
            material["Value 2"],
            material["Value 3"],
            material["Value 4"]
        )
        terrain.materials.materials.append(mat)
        
        if import_textures:
            if name1.upper() not in bw_textures and name1.upper() not in existing_textures:
                bw1tex = bwtex.BW1Texture.from_blender_image(
                    material.node_tree.nodes["texturemain"].image,
                    name1.upper(),
                    "DXT1")
                bw_textures[name1.upper()] = bw1tex
                newid = choose_unique_id(1100000000, cummulative_ids)
                cummulative_ids.append(newid)
                level_xml.add_texture(name1.upper(), newid)
                
            if name2.upper() not in bw_textures and name2.upper() not in existing_textures:
                bw2tex = bwtex.BW1Texture.from_blender_image(
                    material.node_tree.nodes["texturedetail"].image,
                    name2.upper(),
                    "DXT1")
                bw_textures[name2.upper()] = bw2tex
                
                newid = choose_unique_id(1100000000, cummulative_ids)
                cummulative_ids.append(newid)
                level_xml.add_texture(name2.upper(), newid)
                
    start = timeit.default_timer()
    if import_textures:
        for texname, tex in bw_textures.items():
            data = BytesIO()
            tex.write(data)
            data.seek(0)
            bwtex_entry = TextureBW1.from_file_headerless(data)
            arc.textures.textures.append(bwtex_entry)
            print("added", bwtex_entry.name)

        
    
    

    print("passed: ", timeit.default_timer()-start)



    for objname, obj, remap in obj_remap_tables:
        if obj.get("BattalionWars", False):
            vtx_count = len(obj.data.vertices)
            size = int(vtx_count**0.5)
            assert vtx_count**0.5 % 1 == 0, "needs to be a square number"
            assert size % 4 == 0, "needs to be a multiple of 4"
            
            base_x = int((obj.location[0] + 2048))//4
            base_y = int((obj.location[1] + 2048))//4
            
            print(obj.name, base_x, base_y)
            get_height = obj.vertex_groups["Height"].weight
            get_mat_index = obj.vertex_groups["Material"].weight
            add_mat = obj.vertex_groups["Material"].add
            get_delete = obj.vertex_groups["Delete"].weight
            vtx_color = obj.data.color_attributes["Color"].data
            blend = obj.data.color_attributes["Blend"].data
            
            detail = obj.data.uv_layers['UVDetail']
            main = obj.data.uv_layers['UVMain']
            
            chunk_delete = []
            chunk_add = []
            for ix in range(size):
                x = base_x + ix# - (base_x + ix)//4
                
                for iy in range(size):
                    y = base_y + iy# - (base_y + iy)//4
                    
                    if 0 <= base_x + ix < 1024 and 0 <= base_y + iy < 1024:
                        cx = y // 16 
                        cy = x // 16
                        
                        tile_x = x % 16 
                        tile_y = y % 16
                        
                        in_tile_x = x % 4 
                        in_tile_y = y % 4
                        
                        local_index = iy + ix*size
                        deleted = try_get(get_delete, (iy//16)*16 + (ix//16)*16*size)
                        if deleted is None or deleted <= 0.5:
                            chunk_add.append(local_index)
                            
                            chunk = terrain.get_chunk(cx, cy, create_if_no_exist=True)
                            if chunk is not None:
                                tile = chunk.tiles[tile_x//4 + (tile_y//4)*4]
                                
                                
                                
                                if in_tile_x == 0 and in_tile_y == 0:
                                    mat_indices = {}
                                    
                                    """for iiy in range(4):
                                        for iix in range(4):
                                            
                                            material = try_get(get_mat_index, (iy+iiy) + (ix+iix)*size)
                                            if material is not None:
                                                matindex = int(round(material*100))
                                                if matindex not in mat_indices:
                                                    mat_indices[matindex] = 1
                                                else:
                                                    mat_indices[matindex] += 1
                                    biggest = 0 
                                    material = None 
                                    for mat, count in mat_indices.items():
                                        if count > biggest:
                                            biggest = count 
                                            material = mat """
                                    material = try_get(get_mat_index, (iy) + (ix)*size)
                                    if material is not None:
                                        material = int(round(material*100))
                                        tile.material_index = remap[material]
                                        add_mat([(iy+iiy) + (ix+iix)*size for iiy in range(4) for iix in range(4)], material/100.0, "REPLACE")
                                                
                                
                                height = try_get(get_height, local_index)
                                if height is not None:
                                    tile.heights[in_tile_x + in_tile_y*4] = int(height*512*16) 
                                
                                color = vtx_color[local_index].color
                                alpha = blend[local_index].color[3]
                                
                                orig_color = tile.colors[in_tile_x + in_tile_y*4]
                                orig_color.r = int(color[0]*255)
                                orig_color.g = int(color[1]*255)
                                orig_color.b = int(color[2]*255)
                                orig_color.a = int(alpha*255)
                        else:
                            terrain.set_chunk_exist_status(cx, cy, False)
                            chunk_delete.append(local_index)
            
            obj.vertex_groups["Delete"].add(chunk_delete, 1.0, "REPLACE")
            obj.vertex_groups["Delete"].add(chunk_add, 0.0, "REPLACE")
            
            for face in obj.data.polygons:
                for vtx_i, loop_i in zip(face.vertices, face.loop_indices):
                    local_x = vtx_i//size
                    local_y = vtx_i%size
                    
                    x = base_x + local_x 
                    y = base_y + local_y
                    
                    cx = y // 16 
                    cy = x // 16
                    
                    if 0 <= x < 1024 and 0 <= y < 1024:
                        chunk = terrain.get_chunk(cx, cy)
                        
                        if chunk is not None:
                            tile_x = x % 16 
                            tile_y = y % 16
                            
                            in_tile_x = x % 4 
                            in_tile_y = y % 4
                            
                            
                            tile = chunk.tiles[tile_x//4 + (tile_y//4)*4]
                        
                            uv_detail = detail.data[loop_i].uv
                            
                            
                            uv = tile.detail_coordinates[(in_tile_x) + (in_tile_y)*4]
                            uv.x, uv.y = uv_detail
                            uv.y = 1 - uv.y
                            
                            if not (value_test(uv.x) and value_test(uv.y)):
                                tile_loc_x = local_x*4
                                tile_loc_y = local_y*4
                                print(uv_detail, "->", uv)
                                raise RuntimeError(f"Tile has Detail UVs out of range: {tile_loc_x},{tile_loc_y} in {obj.name}")
                            
                            if (in_tile_x == 0 or in_tile_x == 3) and (in_tile_y == 0 or in_tile_y == 3):
                                uv_main = main.data[loop_i].uv
                                iix = (in_tile_x // 3)
                                iiy = in_tile_y // 3
                                uv = tile.surface_coordinates[iix + iiy*2]
                                uv.x, uv.y = uv_main
                                uv.y = 1 - uv.y
                                
                                if not (value_test(uv.x) and value_test(uv.y)):
                                    tile_loc_x = local_x*4
                                    tile_loc_y = local_y*4
                                    print(uv_main, "->", uv)
                                    raise RuntimeError(f"Tile has Main UVs out of range: {tile_loc_x},{tile_loc_y} in {obj.name}")
                                
    print(len(terrain.materials.materials), "Materials")
    """
    obj = bpy.context.selected_objects[0]
    get_weight = obj.vertex_groups["Height"].weight
    get_mat_index = obj.vertex_groups["Material"].weight

    vtx_color = obj.data.color_attributes["Color"].data

    for cx in range(64):
        for cy in range(64):
            entry = terrain.chunkmap.entries[cx][cy]
            if entry.chunk_exists():
                chunk = terrain.chunks.chunks[entry.index]
                for ix in range(16):
                    for iy in range(16):
                        x = cx*16 + ix 
                        y = cy*16 + iy 
                        
                        try:
                            height = get_weight(x + y*1024)*512.0
                        except RuntimeError:
                            height = 0.0
                        
                        tx = ix // 4 
                        ty = iy // 4
                        tix = ix % 4 
                        tiy = iy % 4
                        
                        tile = chunk.tiles[4*tx + ty]
                        
                        tile .heights[tix*4+tiy] = int(height*16)
                        mat_index = get_mat_index((x-tix) + (y-tiy)*1024)
                        tile.material_index = int(mat_index*100)
                        
                        color = vtx_color[x + y*1024].color
                        orig_color = tile.colors[tix*4+tiy]
                        orig_color.r = int(color[0]*255)
                        orig_color.g = int(color[1]*255)
                        orig_color.b = int(color[2]*255)
                        orig_color.a = int(color[3]*255)"""


    new = binaryreader.BinaryReader()
    #terrain.regenerate_collmap()
    new.write_object(terrain)
    
    if import_textures:
        tmp_xml = BytesIO()
        level_xml.write(tmp_xml)
        tmp_xml.seek(0)
        
        tmp_arc = BytesIO()
        arc.write(tmp_arc)
        tmp_arc.seek(0)
        with open_path(dest_res, "wb") as f:
            f.write(tmp_arc.getvalue())
        print("Saved res to", dest_res)
        
        with open_path(dest_xml, "wb") as f:
            f.write(tmp_xml.getvalue())
        print("Saved xml to", dest_xml)
            
    with open(dest, "wb") as f:
        f.write(new.getvalue())
        print("Saved out to", dest)
"""        
if __name__ == "__main__":
    outpathBW = r"D:\Wii games\BattWars\P-G8WP\files\Data\CompoundFiles\C1_OnPatrol.out"

    respathBW = outpathBW.replace(".out", "_Level.res.gz")
    if not os.path.exists(respathBW):
        respathBW = outpathBW.replace(".out", "_Level.res")

        if not os.path.exists(respathBW):
            respathBW = None 
    
    export_terrain(outpathBW, respathBW)"""