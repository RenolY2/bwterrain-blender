bl_info = {
    "name": "Battalion Wars Terrain Addon",
    "version": (1, 0, 0),
    "blender": (4, 50, 0),
    "category": "Import-Export",
    "warning": "Import can take some time (>15 sec)"
}

import bpy
import bmesh 
import os 
import time 

from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       IntProperty,
                       PointerProperty,
                       )
from bpy_extras.io_utils import ExportHelper

import gzip
import importlib
from io import BytesIO

from . import bwterrain 
importlib.reload(bwterrain)
from .bwterrain import bw_terrain
importlib.reload(bwterrain)

from dataclasses import dataclass
from .bwterrain.bwarchivelib import BattalionArchive
from timeit import default_timer 


from .bwterrain import bwtex
from .bwterrain import bwarchivelib
from .bwterrain.texlib import texture_utils
from .terrain_tools import rename, sew_terrain, reset_uv_selected_objects

from .write_terrain import export_terrain

importlib.reload(texture_utils)
importlib.reload(bwarchivelib)
importlib.reload(bwtex)


TEST_RUN = False


respathBW2 = r"D:\Wii games\BWNAExtracted\DATA\files\Data\CompoundFiles\SP_3.4_Level.res.gz"
respathBW = r"D:\Wii games\BattWars\P-G8WP\files\Data\CompoundFiles\C1_Bonus_Level.res"


def open_path(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rb") 
    else:
        return open(path, "rb") 


def make_placeholder_image(name):
    return bpy.data.images.new(name, 32, 32)


def load_tex(arc, tex):
    data = BytesIO(tex.data)
    name = tex.name 
    
    if arc.textures.is_bw1:
        texture = bwtex.BW1Texture.from_file(name, data, ignoremips=True)
    else:
        texture = bwtex.BW2Texture.from_file(name, data, ignoremips=True)
        
    img = texture.mipmaps[0].image 
    img.name = name
    
    return img


importlib.reload(bw_terrain)

@dataclass
class FullPathMaterial:
    texmain: object 
    texmainname: str
    texdetail: object
    texdetailname: str
    bwmat: object
    

def main(context):
    for obj in context.scene.objects:
        print(obj)



class UIDemo(bpy.types.Operator):
    bl_idname = "object.simpleui"
    bl_label = "Simple Test"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None 
     
    def invoke(self, context,event):
        return context.window_manager.invoke_props_popup(self, event)
    
    def execute(self, context):
        main(context)
        return {"FINISHED"}


def register():
    bpy.utils.register_class(UIDemo)


def unregister():
    bpy.utils.unregister_class(UIDemo)


def make_mesh_grid(x, y, z, xsize, ysize, tilesize):
    vtx = []
    faces = []
    for ix in range(xsize):
        for iy in range(ysize):
            offsetx = ix//4
            offsety = iy//4
            
            pos = (x+(ix-offsetx)*tilesize, y+(iy-offsety)*tilesize, z)
            vtx.append(pos)
            
            if (ix < xsize-1 and iy < ysize-1
                and ((ix+1)%4 != 0 and (iy+1) % 4 != 0)):
                faces.append(
                    (ix*ysize + iy, 
                    (ix+1)*ysize + iy,
                    (ix+1)*ysize + (iy+1),
                    ix*ysize + (iy+1))
                    )
    
    return vtx, faces
            

def make_layout(rows, horiz_spacing, vert_spacing, x_start=0, y_start=0):
    offsety = y_start
    
    for row in rows:
        offsetx = x_start
        for node in row:
            if node is not None:
                node.location[0:2] = (offsetx, offsety)
            
            offsetx += horiz_spacing 
        
        offsety += vert_spacing    


class Connector(object):
    def __init__(self, node_tree):
        self.node_tree = node_tree 
        
    def _connect(self, 
                out_node, out_field,
                in_node, in_field):
        self.node_tree.links.new(
            out_node.outputs[out_field],
            in_node.inputs[in_field])
            
    def connect(self, 
                *links):
        last_node, last_field = None, None 
        
        for i in range(0, len(links), 2):
            node, field = links[i:i+2] 
            if isinstance(field, (str, int)):
                field = (field, field)
            
            if last_node is not None and last_field is not None:
                self._connect(last_node, last_field[1],
                                node, field[0])
            last_node = node 
            last_field = field 


class NodeCreator(object):
    def __init__(self, nodes):
        self.nodes = nodes 
    
    def new(self, nodename, inputs=[], **kwargs):
        node = self.nodes.new(nodename)
        for field, val in kwargs.items():
            setattr(node, field, val)
        
        for i, val in inputs:
            node.inputs[i].default_value = val
        
        return node


def create_empty_material():
    material = bpy.data.materials.new(name="DELETED TERRAIN")
    material.use_nodes = True
    material.node_tree.nodes["Principled BSDF"].inputs[4].default_value = 0.0
    
    return material 


def create_terrain_material(name, tex1, tex2):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    material.node_tree.nodes.remove(
        material.node_tree.nodes["Principled BSDF"])
        
    connector = Connector(material.node_tree)
    connect = connector.connect        

    mat_output =  material.node_tree.nodes["Material Output"]
    
    creator = NodeCreator(material.node_tree.nodes)
    
    vertex_color_mix = material.node_tree.nodes.new("ShaderNodeMix")
    vertex_color_mix.data_type = "RGBA"
    vertex_color_mix.blend_type = "MULTIPLY"
    vertex_color_mix.inputs[0].default_value = 1.0
    
    
    
    

    texture_mix = material.node_tree.nodes.new("ShaderNodeMix")
    texture_mix.data_type = "RGBA"
    texture_mix.blend_type = "MIX"

    connect(texture_mix, "Result", 
            vertex_color_mix, "A")
    
    placeholder_tex_preview_mix = creator.new("ShaderNodeMix", data_type="RGBA", blend_type="MIX", name="PreviewMix")

    texture1 = material.node_tree.nodes.new("ShaderNodeTexImage")
    texture1.name = texture1.label = "texturemain"
    texture2 = material.node_tree.nodes.new("ShaderNodeTexImage")
    texture2.name = texture2.label = "texturedetail"
    
    
    texture1.image = tex1
    texture2.image = tex2
    
    uv_main = material.node_tree.nodes.new("ShaderNodeUVMap")
    uv_detail = material.node_tree.nodes.new("ShaderNodeUVMap")
    uv_default = material.node_tree.nodes.new("ShaderNodeUVMap")
    
    uv_main.uv_map = "UVMain"
    uv_detail.uv_map = "UVDetail"
    
    uv_main_mix = material.node_tree.nodes.new("ShaderNodeMix")
    uv_main_mix.data_type = "VECTOR"
    uv_detail_mix = material.node_tree.nodes.new("ShaderNodeMix")
    uv_detail_mix.data_type = "VECTOR"
    
    connect(uv_default, "UV",
        uv_main_mix, "A")
    connect(uv_default, "UV",
        uv_detail_mix, "A")
    
    connect(uv_main, "UV",
        uv_main_mix, "B")
    connect(uv_detail, "UV",
        uv_detail_mix, "B")
    
    vtx_color = material.node_tree.nodes.new("ShaderNodeVertexColor")
    vtx_color.layer_name = "Color"
    
    blend = material.node_tree.nodes.new("ShaderNodeVertexColor")
    blend.layer_name = "Blend"
    
    greater_than = material.node_tree.nodes.new("ShaderNodeMath")
    greater_than.operation = "GREATER_THAN"
    greater_than.inputs[1].default_value = 0.0
    
    separate_vec = creator.new("ShaderNodeSeparateXYZ")
    greater_than_half = creator.new("ShaderNodeMath", operation="GREATER_THAN", inputs=[(1, 0.5)])
    
    
    # Set up nodes for blend mode override
    blendmode_attr = creator.new("ShaderNodeAttribute", attribute_name="BlendMode")
    less_than = creator.new("ShaderNodeMath", operation="LESS_THAN", inputs=[(1, 0.0)])
    blendmode_mix = creator.new("ShaderNodeMix")
    
    make_layout([
        [None, less_than],
        [blendmode_attr, None, blendmode_mix]],
        300, -300, y_start=300)
    
    connect(blendmode_attr, "Fac",
            less_than, "Value")
    connect(blendmode_attr, "Fac",
            blendmode_mix, "A")
    connect(less_than, "Value",
            blendmode_mix, "Factor")
    
    connect(uv_default, "UV",
            separate_vec, "Vector")
    connect(separate_vec, "X",
            greater_than_half, "Value")
    
    
    connect(greater_than_half, "Value",
            placeholder_tex_preview_mix, "Factor")
    connect(texture1, "Color",
            placeholder_tex_preview_mix, "A")
    connect(texture2, "Color",
            placeholder_tex_preview_mix, "B")
    
    color_length = material.node_tree.nodes.new("ShaderNodeVectorMath")
    color_length.operation = "LENGTH"
    
    
    placeholder_mix = material.node_tree.nodes.new("ShaderNodeMix")
    placeholder_mix.data_type = "RGBA"
    placeholder_mix.blend_type = "MIX"
    
    connect(vertex_color_mix, "Result",
            placeholder_mix, "B")
    
    connect(placeholder_mix, "Result",
            mat_output, "Surface")
    
    connect(placeholder_tex_preview_mix, "Result",
            placeholder_mix, "A")
    
    connect(greater_than, "Value",
        uv_main_mix, "Factor")
    connect(greater_than, "Value",
        uv_detail_mix, "Factor")
    
    connect(greater_than, "Value",
            placeholder_mix, "Factor")
    
    connect(vtx_color, "Color", 
            color_length, "Vector")
    
    connect(color_length, "Value", 
            greater_than, "Value")
    
    connect(greater_than, "Value", 
            placeholder_mix, "Factor")
    
    connect(vtx_color, "Color", 
            vertex_color_mix, "B")
            
    connect(greater_than, "Value", 
            vertex_color_mix, "Factor")
            
    connect(blend, "Alpha", 
            blendmode_mix, ("B", "Result"),
            texture_mix, "Factor")
            
    connect(texture1, "Color",
            texture_mix, "A")
    connect(texture2, "Color",
            texture_mix, "B")
        
    connect(uv_main_mix, "Result",
            texture1, "Vector")
    connect(uv_detail_mix, "Result",
            texture2, "Vector")
    
    color_mult_4 = material.node_tree.nodes.new("ShaderNodeVectorMath")
    color_mult_4.operation = "MULTIPLY"
    
    color_square = material.node_tree.nodes.new("ShaderNodeVectorMath")
    color_square.operation = "MULTIPLY"
    
    
    connect(color_mult_4, "Vector",
            color_square, 0)
    color_mult_4.inputs[1].default_value = (4.0, 4.0, 4.0)
    
    connect(color_mult_4, "Vector",
            color_square, 1)
    connect(color_mult_4, "Vector",
            color_square, 0)
    connect(color_square, "Vector",
            vertex_color_mix, "B")
    connect(vtx_color, "Color", 
            color_mult_4, "Vector")
            
    
    make_layout([
        [None, greater_than_half],
        [vtx_color, color_length, placeholder_tex_preview_mix, color_mult_4, color_square],
        [uv_default, separate_vec, greater_than, vertex_color_mix, placeholder_mix, mat_output],
        [uv_main, uv_main_mix, texture1, texture_mix, None],
        [uv_detail, uv_detail_mix, texture2, None, None]
        ], 300, -300)
    blend.location[0] = vtx_color.location[0]
    blend.location[1] = vtx_color.location[1] + 100
    material.preview_render_type = "FLAT"
    
    return material

class TerrainGrid(object):
    def __init__(self, 
    name, 
    offset, 
    sizex, 
    sizey, 
    scale, 
    heightscale,
    materials,
    geonode=None
        ):
        mesh_data = bpy.data.meshes.new(name=f"{name}_mesh")
        mesh_obj = bpy.data.objects.new(name, mesh_data)
        mesh_obj["BattalionWars"] = True
        mesh_obj.location = (offset[0], offset[1], 0.0)
        
        self.offset = offset 
        self.sizex = sizex 
        self.sizey = sizey
        self.scale = scale
        self.mesh_obj = mesh_obj 
        
        bpy.context.scene.collection.objects.link(mesh_obj)
        
        bm = bmesh.new()
        offset[0], offset[1]
        vtxlist, faces = make_mesh_grid(0, 0, 0, sizex, sizey, scale)
        for pos in vtxlist:
            bm.verts.new(pos)
        
        bm.verts.ensure_lookup_table()
        
        for face in faces:
            bm.faces.new([bm.verts[i] for i in face])
        
        bm.to_mesh(mesh_data)
        mesh_data.update()
        bm.free()
        
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.node.new_geometry_nodes_modifier()
        mesh_obj.modifiers["GeometryNodes"].name = "TerrainRenderer"
            
        
        
        bpy.ops.object.vertex_group_add()
        bpy.ops.object.vertex_group_add()
        bpy.ops.object.vertex_group_add()
        
        mesh_obj.vertex_groups["Group"].name = "Height"
        mesh_obj.vertex_groups["Group.001"].name = "Delete"
        mesh_obj.vertex_groups["Group.002"].name = "Material"
        
        bpy.ops.mesh.uv_texture_add()
        bpy.ops.mesh.uv_texture_add()
        
        mesh_obj.data.uv_layers["UVMap"].name = "UVMain"
        mesh_obj.data.uv_layers["UVMap.001"].name = "UVDetail"
        
        bpy.ops.geometry.color_attribute_add(name="Blend", data_type="BYTE_COLOR")
        bpy.ops.geometry.color_attribute_add(name="Color", data_type="BYTE_COLOR")
        
        
        for mat in materials:
            mesh_obj.data.materials.append(mat)
            
        mod = mesh_obj.modifiers["TerrainRenderer"]
        if geonode is not None:
            mesh_obj.modifiers["TerrainRenderer"].node_group = geonode.node_group
        
        else:
            geo_nodegroup = mesh_obj.modifiers["TerrainRenderer"].node_group
            geo_nodegroup.interface.new_socket(socket_type="NodeSocketFloat", name="VertexHeight", in_out="INPUT")
            geo_nodegroup.interface.new_socket(socket_type="NodeSocketFloat", name="Delete", in_out="INPUT")
            geo_nodegroup.interface.new_socket(socket_type="NodeSocketFloat", name="MaterialIndex", in_out="INPUT")
            geo_nodegroup.interface.new_socket(socket_type="NodeSocketInt", name="BlendMode", in_out="INPUT",
                description=("Sets the blend mode override for the terrain."
                            "\n-1 = Normal blending \n"
                            "0 = Only show main texture\n"
                            "1 = Only show detail texture"))
            
            geo_nodegroup.interface.items_tree[5].min_value = -1
            geo_nodegroup.interface.items_tree[5].max_value = 1
            geo_nodegroup.interface.items_tree[5].default_value = -1
        
        bpy.ops.object.geometry_nodes_input_attribute_toggle(input_name="Socket_2", modifier_name="TerrainRenderer")
        bpy.ops.object.geometry_nodes_input_attribute_toggle(input_name="Socket_3", modifier_name="TerrainRenderer")
        bpy.ops.object.geometry_nodes_input_attribute_toggle(input_name="Socket_4", modifier_name="TerrainRenderer") 
        mesh_obj.modifiers["TerrainRenderer"]["Socket_2_attribute_name"] = "Height"
        mesh_obj.modifiers["TerrainRenderer"]["Socket_3_attribute_name"] = "Delete"
        mesh_obj.modifiers["TerrainRenderer"]["Socket_4_attribute_name"] = "Material"
        mesh_obj.modifiers["TerrainRenderer"]["Socket_5"] = -1
        
        if geonode is None:
            material_index = geo_nodegroup.nodes.new("GeometryNodeSetMaterialIndex")
            material_index.name = material_index.label = "material_index"
            
            set_pos_geo = geo_nodegroup.nodes.new("GeometryNodeSetPosition")
            set_pos_geo.name = set_pos_geo.label = "set_pos_geo"
            
            math_compare = geo_nodegroup.nodes.new("FunctionNodeCompare")
            math_compare.name = math_compare.label = "math_compare"
            math_compare.inputs[1].default_value = 0.5
            
            math_heightscale = geo_nodegroup.nodes.new("ShaderNodeMath")
            math_heightscale.name = math_heightscale.label = "math_heightscale"
            math_heightscale.operation = "MULTIPLY"
            math_heightscale.inputs[1].default_value = heightscale
            
            math_matindex_multiply = geo_nodegroup.nodes.new("ShaderNodeMath")
            math_matindex_multiply.name = math_matindex_multiply.label = "math_matindex_multiply"
            math_matindex_multiply.operation = "MULTIPLY"
            math_matindex_multiply.inputs[1].default_value = 100
            
            math_matindex_round = geo_nodegroup.nodes.new("ShaderNodeMath")
            math_matindex_round.name = math_matindex_round.label = "math_matindex_round"
            math_matindex_round.operation = "ROUND"
            
            combine = geo_nodegroup.nodes.new("ShaderNodeCombineXYZ")
            combine.name = combine.label = "combine"
            
            store_attribute = geo_nodegroup.nodes.new("GeometryNodeStoreNamedAttribute")
            store_attribute.name = store_attribute.label = "store_attribute"
            store_attribute.data_type = "INT"
            store_attribute.inputs[2].default_value = "BlendMode"
            
            
            
            creator = NodeCreator(geo_nodegroup.nodes)
            # Set position to multiple of 64 
            self_obj = creator.new("GeometryNodeSelfObject")
            obj_info = creator.new("GeometryNodeObjectInfo")
            modulo_64 = creator.new("ShaderNodeVectorMath", operation="MODULO")
            modulo_64.inputs[1].default_value[0] = modulo_64.inputs[1].default_value[1] = 64.0 
            modulo_64.inputs[1].default_value[2] = 1.0
            
            multiply_minus_1 = creator.new("ShaderNodeVectorMath", operation="MULTIPLY")
            multiply_minus_1.inputs[1].default_value[0] = multiply_minus_1.inputs[1].default_value[1] = -1
            obj_transform = creator.new("GeometryNodeTransform")
            ### 
            
            
            ### Draw quad outline 
            convex_hull = creator.new("GeometryNodeConvexHull", name="convex_hull", label="convex_hull")
            delete_faces = creator.new("GeometryNodeDeleteGeometry", name="delete_faces", label="delete_faces")
            delete_faces.mode = "ONLY_FACE"
            
            join_geo = creator.new("GeometryNodeJoinGeometry", name="join_geo", label="join_geo")
            
            ###
            
            # Nodes
            add_1_matindex = creator.new("FunctionNodeIntegerMath", name="add_1_matindex", label="add_1_matindex", operation="ADD")
            add_1_matindex.inputs[0].default_value = 0
            add_1_matindex.inputs[1].default_value = 1
            add_1_matindex.inputs[2].default_value = 0
            mix_matindex_and_delete = creator.new("ShaderNodeMix", name="mix_matindex_and_delete", label="mix_matindex_and_delete")
            
            
            connector = Connector(geo_nodegroup)
            connect = connector.connect 
            connect(material_index, "Geometry",
                    store_attribute, "Geometry",
                    obj_transform, "Geometry",
                    join_geo, "Geometry",
                    geo_nodegroup.nodes["Group Output"], "Geometry")
            
            connect(geo_nodegroup.nodes["Group Input"], "BlendMode",
                    store_attribute, "Value")
            
            connect(set_pos_geo, "Geometry",
                    material_index, "Geometry")
            
            connect(math_compare, "Result",
                    mix_matindex_and_delete, "Factor")
                    
            connect(mix_matindex_and_delete, "Result",
                    material_index, "Material Index")
            
            connect(combine, "Vector",
                    set_pos_geo, "Offset")
            
            connect(math_heightscale, "Value",
                    combine, "Z")
            
            connect(math_matindex_round, "Value", 
                    add_1_matindex, 0)
                
            connect(geo_nodegroup.nodes["Group Input"], "Delete",
                    math_compare, "A")
            
            connect(math_matindex_multiply, "Value",
                    math_matindex_round, "Value")
                    
            connect(geo_nodegroup.nodes["Group Input"], "MaterialIndex",
                    math_matindex_multiply, "Value")
            
            connect(geo_nodegroup.nodes["Group Input"], "VertexHeight",
                    math_heightscale, "Value")
                    
            connect(geo_nodegroup.nodes["Group Input"], "Geometry",
                    set_pos_geo, "Geometry")
            
            connect(self_obj, "Self Object",
                    obj_info, "Object")
                    
            connect(obj_info, "Location",
                    modulo_64, "Vector")
            
            connect(modulo_64, "Vector",
                    multiply_minus_1, "Vector")
            
            connect(multiply_minus_1, "Vector",
                    obj_transform, "Translation")    
            connect(geo_nodegroup.nodes["Group Input"], "Geometry",
                    convex_hull, "Geometry")
            connect(convex_hull, "Convex Hull",
                    delete_faces, "Geometry",
                    join_geo, "Geometry")
                    
            
            
            
            
            # Connections
            connect(add_1_matindex, "Value",
                  mix_matindex_and_delete, "A")
            # Locations
            add_1_matindex.location[0:2] = (620.0, -800.0)
            mix_matindex_and_delete.location[0:2] = (820.0, -400.0)
            
            
            
            
            
            make_layout([
                [self_obj, obj_info, modulo_64, multiply_minus_1, None, None, obj_transform],
                [None,                                  math_compare,  None, mix_matindex_and_delete],
                [geo_nodegroup.nodes["Group Input"],    math_heightscale, combine, set_pos_geo, material_index, store_attribute, None, geo_nodegroup.nodes["Group Output"]],
                [None,                                  math_matindex_multiply,   math_matindex_round,               add_1_matindex],
                [None, None, None, None, convex_hull, delete_faces, join_geo]
                ], 200, -300)

            
            # Nodes
            vtx_index = creator.new("GeometryNodeInputIndex", name="vtx_index", label="vtx_index")
            eval_at_index = creator.new("GeometryNodeFieldAtIndex", name="eval_at_index", label="eval_at_index", domain="FACE")
            eval_at_index.inputs[0].default_value = 0.0
            eval_at_index.inputs[1].default_value = 0
            modulo_x = creator.new("ShaderNodeMath", name="modulo_x", label="modulo_x", operation="FLOORED_MODULO")
            modulo_x.inputs[1].default_value = 4.0
            modulo_y = creator.new("ShaderNodeMath", name="modulo_y", label="modulo_y", operation="DIVIDE")
            modulo_y.inputs[1].default_value = 256.0
            vtx_length = creator.new("FunctionNodeInputInt", name="vtx_length", label="vtx_length")
            vtx_length.integer = 192
            mult_y_192 = creator.new("ShaderNodeMath", name="mult_y_192", label="mult_y_192", operation="MULTIPLY")
            mult_y_192.inputs[1].default_value = 1024.0
            add_x_y = creator.new("ShaderNodeMath", name="add_x_y", label="add_x_y", operation="ADD")
            add_x_y.inputs[1].default_value = 4.0
            snap_4_x = creator.new("ShaderNodeMath", name="snap_4_x", label="snap_4_x", operation="SNAP")
            snap_4_x.inputs[1].default_value = 3.0
            snap_4_y = creator.new("ShaderNodeMath", name="snap_4_y", label="snap_4_y", operation="SNAP")
            snap_4_y.inputs[1].default_value = 3.0
            snap_12_x = creator.new("ShaderNodeMath", name="snap_12_x", label="snap_12_x", operation="SNAP")
            snap_12_x.inputs[1].default_value = 12.0
            snap_12_y = creator.new("ShaderNodeMath", name="snap_12_y", label="snap_12_y", operation="SNAP")
            snap_12_y.inputs[1].default_value = 12.0
            mult_y_192_delete = creator.new("ShaderNodeMath", name="mult_y_192_delete", label="mult_y_192_delete", operation="MULTIPLY")
            mult_y_192_delete.inputs[1].default_value = 256.0
            add_x_y_delete = creator.new("ShaderNodeMath", name="add_x_y_delete", label="add_x_y_delete", operation="ADD")
            add_x_y_delete.inputs[1].default_value = 4.0
            eval_at_index_delete = creator.new("GeometryNodeFieldAtIndex", name="eval_at_index_delete", label="eval_at_index_delete", domain="FACE")
            eval_at_index_delete.inputs[0].default_value = 0.0
            eval_at_index_delete.inputs[1].default_value = 0
            # Connections
            connect(vtx_index, "Index",
                  modulo_x, "Value")

            connect(vtx_length, "Integer",
                  modulo_x, 1)

            connect(mult_y_192, "Value",
                  add_x_y, 1)
            connect(modulo_x, "Value",
                  snap_4_x, "Value")
            connect(snap_4_y, "Value",
                  mult_y_192, "Value")

            connect(vtx_length, "Integer",
                  mult_y_192, 1)

            connect(vtx_length, "Integer",
                  modulo_y, 1)
            connect(modulo_y, "Value",
                  snap_4_y, "Value")
            connect(vtx_index, "Index",
                  modulo_y, "Value")
            connect(add_x_y, "Value",
                  eval_at_index, "Index")
            connect(snap_4_x, "Value",
                  add_x_y, "Value")
            connect(geo_nodegroup.nodes["Group Input"], "MaterialIndex",
                  eval_at_index, "Value")
            connect(eval_at_index, "Value",
                  math_matindex_multiply, "Value")

            connect(mult_y_192_delete, "Value",
                  add_x_y_delete, 1)
            connect(snap_12_y, "Value",
                  mult_y_192_delete, "Value")
            connect(snap_12_x, "Value",
                  add_x_y_delete, "Value")
            connect(geo_nodegroup.nodes["Group Input"], "Delete",
                  eval_at_index_delete, "Value")
            connect(add_x_y_delete, "Value",
                  eval_at_index_delete, "Index")

            connect(vtx_length, "Integer",
                  mult_y_192_delete, 1)
            connect(eval_at_index_delete, "Value",
                  math_compare, "A")
            connect(modulo_x, "Value",
                  snap_12_x, "Value")
            connect(modulo_y, "Value",
                  snap_12_y, "Value")
            # Locations
            vtx_index.location[0:2] = (-1660.0, -1080.0)
            eval_at_index.location[0:2] = (-120.0, -980.0)
            modulo_x.location[0:2] = (-1260.0, -800.0)
            modulo_y.location[0:2] = (-1260.0, -1080.0)
            vtx_length.location[0:2] = (-1680.0, -900.0)
            mult_y_192.location[0:2] = (-740.0, -1040.0)
            add_x_y.location[0:2] = (-420.0, -1020.0)
            snap_4_x.location[0:2] = (-1020.0, -800.0)
            snap_4_y.location[0:2] = (-1040.0, -1080.0)
            snap_12_x.location[0:2] = (-840.0, -180.0)
            snap_12_y.location[0:2] = (-840.0, -480.0)
            mult_y_192_delete.location[0:2] = (-600.0, -460.0)
            add_x_y_delete.location[0:2] = (-320.0, -240.0)
            eval_at_index_delete.location[0:2] = (-60.0, -300.0)
            


def matchtex(tex, texlist):
    texlow = tex.lower()
    for i in texlist:
        if i.split(".")[0].lower() == tex:
            return i


class Timer(object):
    def __init__(self):
        self.last = default_timer()
    
    def passed(self):
        curr = default_timer()
        passed = curr - self.last
        self.last = curr 
        return passed 


def import_terrain(terr_path, res_path, progress_update=None, cached_textures=None):
    timer = Timer()
    with open_path(res_path) as f:
        arc = bwarchivelib.BattalionArchive.from_file_textures(f)
    print("Textures from .res loaded in", timer.passed())
    progress_update(0.1)
    bwtextures = {}
    for tex in arc.textures.textures:
        bwtextures[tex.name.lower()] = tex 
    
    
    #textures = os.listdir(texfolder)
    
    with open(terr_path, "rb") as f:
        terrain = bw_terrain.BWTerrainV2(f)
    
    progress_update(0.2)
    start = default_timer()
    print("Terrain loaded in", timer.passed())
    texlist = {}
    
    
    materials = []
    loaded_texts = {}
    sorted_materials = [mat for mat in terrain.materials]
    sorted_materials.sort(key=lambda mat: mat.mat1+mat.mat2) 
    remap = {}
    for i, mat in enumerate(terrain.materials):
        remap[i] = sorted_materials.index(mat)
    
    if cached_textures:
        for mat in sorted_materials:
            for tex in (mat.mat1, mat.mat2):
                if tex.lower() in cached_textures and tex not in loaded_texts:
                    bpy.ops.image.open(filepath=cached_textures[tex.lower()],
                                        use_udim_detecting=False)
                    loaded_texts[tex] = bpy.data.images[os.path.basename(cached_textures[tex])]
    
    
    
    for mat in sorted_materials:
        tex1 = load_tex(arc, bwtextures[mat.mat1.lower()]) if mat.mat1 not in loaded_texts else loaded_texts[mat.mat1]
        tex2 = load_tex(arc, bwtextures[mat.mat2.lower()]) if mat.mat2 not in loaded_texts else loaded_texts[mat.mat2]
        loaded_texts[mat.mat1] = tex1
        loaded_texts[mat.mat2] = tex2
        
        materials.append(
            FullPathMaterial(
                tex1, mat.mat1, 
                tex2, mat.mat2,
                mat)
        )
    print("Loaded textures in", timer.passed())
    blender_mats = [create_empty_material()]
    for i in range(len(materials)):
        mat = create_terrain_material(
                f"Mat{i:02}_{materials[i].texmainname}_{materials[i].texdetailname}", 
                materials[i].texmain, 
                materials[i].texdetail)
        mat["Value 1"] = materials[i].bwmat.unk1
        mat["Value 2"] = materials[i].bwmat.unk2
        mat["Value 3"] = materials[i].bwmat.unk3
        mat["Value 4"] = materials[i].bwmat.unk4
        blender_mats.append(mat)
    
    print("Set up materials in", timer.passed())
    #register()
    #bpy.ops.object.simpleui("INVOKE_DEFAULT")
    name = os.path.basename(terr_path).replace(".out", "")
    
    PARTS = 4
    
    geonode = None 
    progress_update(0.3)    
    
    for px in range(PARTS):
        for py in range(PARTS):
            timer.passed()
            grid = TerrainGrid(f"{name}_{px}_{py}", (-2048+(4096/PARTS)*px, -2048+(4096/PARTS)*py, 0), 64*16//PARTS, 64*16//PARTS, 4*(4/3), 512,
                                blender_mats, geonode)
            
            if geonode is None:
                geonode = grid.mesh_obj.modifiers["TerrainRenderer"]
                    
            group = grid.mesh_obj.vertex_groups["Height"]
            print("Created grid in", timer.passed())
            
            PARTSIZE = 1024//PARTS
            PARTSIZE_SMALL = 256//PARTS
            
            # Set the vertex heights and deletion status
            deleted = []
            for x in range(PARTSIZE):
                for y in range(PARTSIZE):
                    index = x*PARTSIZE + y
                    vtx = terrain.pointdata[x+px*PARTSIZE][y+py*PARTSIZE]
                    if vtx is not None:
                        group.add([index], vtx.height/512.0, "REPLACE")
                        #vtx_color[index].color = (vtx.color.r, vtx.color.g, vtx.color.b, vtx.color.a)
                    else:
                        deleted.append(index)
            grid.mesh_obj.vertex_groups["Delete"].add(deleted, 1.0, "REPLACE")         
            print("Set Delete/Height in",  timer.passed())         
                    
                    
            # Set the material indices
            material_index = grid.mesh_obj.vertex_groups["Material"]
            
            for cx in range(PARTSIZE_SMALL):
                for cy in range(PARTSIZE_SMALL):
                    matindex = terrain.material_map[cx+px*PARTSIZE_SMALL][cy+py*PARTSIZE_SMALL]
                    if matindex is not None:
                        matindex = remap[matindex]
                        material_index.add([
                            (cx*4+tx)*PARTSIZE+(cy*4+ty) for tx in range(4) for ty in range(4)
                            ],
                            matindex/100.0, 
                            "REPLACE")
            print("Set Mat index in",  timer.passed())      
            # Set vertex colors
            vtx_color = grid.mesh_obj.data.color_attributes["Color"].data
            
            blend = grid.mesh_obj.data.color_attributes["Blend"].data
            
            for x in range(PARTSIZE):
                for y in range(PARTSIZE):
                    vtx = terrain.pointdata[x+px*PARTSIZE][y+py*PARTSIZE]
                    index = x*PARTSIZE + y
                    if vtx is not None:
                        vtx_color[index].color = (vtx.color.r, vtx.color.g, vtx.color.b, vtx.color.a)
                        blend[index].color = (1.0, 1.0, 1.0, vtx.color.a)
                        
                    else:
                        vtx_color[index].color = (1.0, 1.0, 1.0, 0)
                        blend[index].color = (1.0, 1.0, 1.0, 1.0)
            print("Set vertex color in",  timer.passed())  
            detail = grid.mesh_obj.data.uv_layers['UVDetail']
            main = grid.mesh_obj.data.uv_layers['UVMain']
            
            for face in grid.mesh_obj.data.polygons:
                for vtx_i, loop_i in zip(face.vertices, face.loop_indices):
                    x = vtx_i//PARTSIZE
                    y = vtx_i%PARTSIZE
                    vtx = terrain.pointdata[x+px*PARTSIZE][y+py*PARTSIZE]
                    if vtx is not None:
                        detail.data[loop_i].uv = (vtx.uv_detail.x, 1-vtx.uv_detail.y)
                        main.data[loop_i].uv = (vtx.uv_main.x, 1-vtx.uv_main.y)
            print("Set UV coords in",  timer.passed())  
            
            if TEST_RUN:
                raise RuntimeError("Test run complete")
                
            progress_update(0.3 + ((px*PARTS + py)/(PARTS*PARTS))*0.7)
    print("Total time:", default_timer()-start)


class ExportTerrain(bpy.types.Operator, ExportHelper):
    """Export a BW Terrain file"""
    bl_idname = "export_bw.terrain"
    bl_label = "Export BW Terrain"
    filter_glob: StringProperty(
        default="*.out",
        options={"HIDDEN"},
    ) 
    filename_ext = ".out"
    
    import_textures: BoolProperty(
        name="Import New Textures",
        description=("If enabled, imports new textures into resource archive (.res) and Level.xml located in the same folder.\n"
                    "This will not remove unused terrain textures, they need to be removed manually.\n"
                    "A resource archive and Level xml named after the same level must exist in the same folder already."),
        default=True)
        
    export_selection: BoolProperty(
        name="Only Export Selection",
        description="If enabled, only exports selected terrain chunks.",
        default=False)
    
    export_visible: BoolProperty(
        name="Only Export Visible",
        description="If enabled, only exports visible terrain chunks.",
        default=True) 
    
    def execute(self, context):
        if bpy.context.mode == "EDIT_MESH":
            bpy.ops.object.editmode_toggle()
            
        outpathBW = self.filepath 
        if not os.path.exists(outpathBW):
            raise RuntimeError("You need to overwrite an existing .out file!")
        
        if self.import_textures:
            respathBW = outpathBW.replace(".out", "_Level.res.gz")
            if not os.path.exists(respathBW):
                respathBW = outpathBW.replace(".out", "_Level.res")

                if not os.path.exists(respathBW):
                    raise RuntimeError(f"Cannot import textures: {respathBW} not found")
            
            xmlpathBW = outpathBW.replace(".out", "_Level.xml.gz")
            if not os.path.exists(xmlpathBW):
                xmlpathBW = outpathBW.replace(".out", "_Level.xml")

                if not os.path.exists(xmlpathBW):
                    raise RuntimeError(f"Cannot import textures: {xmlpathBW} not found")
            
            preloadpathBW = outpathBW.replace(".out", "_Level_preload.xml.gz")
            if not os.path.exists(preloadpathBW):
                preloadpathBW = outpathBW.replace(".out", "_Level_preload.xml")

                if not os.path.exists(preloadpathBW):
                    raise RuntimeError(f"Cannot import textures: {preloadpathBW} not found")
        else:
            respathBW = None 
            xmlpathBW = None 
            preloadpathBW = None 
        
        export_terrain(
            outpathBW, 
            respathBW, 
            dest_xml=xmlpathBW, 
            dest_preload_xml=preloadpathBW, 
            selected_only=self.export_selection, 
            visible_only=self.export_visible)
            
        return {"FINISHED"}
        

def adjust_all_areas_clip(start, end):
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    if space.clip_start < start:
                        space.clip_start = start 
                    if space.clip_end < end:
                        space.clip_end = end

class ImportTerrain(bpy.types.Operator, ExportHelper):
    """Import a BW Terrain file"""
    bl_idname = "import_bw.terrain"
    bl_label = "Import BW Terrain"
    filter_glob: StringProperty(
        default="*.out",
        options={"HIDDEN"},
    ) 
    filename_ext = ".out"
    """show_progress: BoolProperty(
        name="Show Progress Bar",
        description="Shows a progress bar while loading the terrain.",
        default=True,)"""
    
    """cached_textures: StringProperty(
        name="Texture Folder",
        description="Path to a texture folder with .png textures (e.g. BW Level Editor's cached textures folder) to speed up loading times.",
        default="")"""
    show_progress = False 
    cached_textures = ""
    
    def execute(self, context):
        terrain_path = self.filepath 
        res_path = self.filepath.replace(".out", "_Level.res")
        
        wm = bpy.context.window_manager
        
        if self.show_progress:       
            bpy.types.WindowManager.progress = bpy.props.FloatProperty()
            bpy.types.VIEW3D_HT_header.append(progress_bar)
            context.window_manager.progress = 0.0 
            wm.progress_begin(0, 100)
            progress = self.set_progress 
            
        
        else:
            progress = self.set_progress_none 
        
        if not os.path.exists(res_path):
            print(terrain_path)
            print(res_path)
            raise RuntimeError("Cannot load terrain without accompanying resource file!")
        
        cached = {}
        
        if self.cached_textures:
            try:
                fnames = os.listdir(self.cached_textures)    
            except:
                pass 
            else:
                print("Checking cached textures...")
                for fname in fnames:
                    if fname.endswith(".png"):
                        texname, _ = fname.split(".", 1)
                        cached[texname.lower()] = os.path.join(self.cached_textures, fname)
                print(f"{len(cached)} cached textures found")
        import_terrain(terrain_path, res_path, progress, cached)
        adjust_all_areas_clip(1.0, 10000.0)
        """
        wm = bpy.context.window_manager
        for i in range(10):
            #wm.progress_update(i)
            progress(i/10.0)
            self.redraw()
            time.sleep(1)"""
        
        
        if self.show_progress:       
            wm.progress_end()
        
            #bpy.types.VIEW3D_HT_header.remove(progress_bar)

        return {"FINISHED"} 
    
    def set_progress_none(self, progress):
        print(f"--- Progress: {progress}% ---") 
        
    def set_progress(self, progress): # Progress from 0.0 to 1.0
        bpy.context.window_manager.progress = progress 
        progress = int(progress*100)
        print(f"--- Progress: {progress}% ---") 
        bpy.context.window_manager.progress_update(progress)
        self.redraw()
        self.redraw()
    
    def redraw(self, context=None):
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        #for a in context.screen.areas:
        #    a.tag_redraw()

        # Force UI update
        """for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()"""

class MESH_OT_SewTerrain(bpy.types.Operator):
    bl_idname = "import_bw.sew_terrain"
    bl_label = "Sew Terrain"
    bl_description = "Sews up tiles for selected terrain chunks. This gets rid of height gaps between tiles and terrain chunks."
    
    selected_only: BoolProperty(
        name="Only On Selected",
        description=("If enabled, imports new textures into resource archive (.res) located in the same folder.\n"
                    "This will not remove unused terrain textures from .res file, they need to be removed manually."),
        default=True)
        
    def execute(self, context):
        sew_terrain(selected_only=True, visible_only=False)
        return {"FINISHED"}


class SynchronizeMaterialNames(bpy.types.Operator):
    bl_idname = "import_bw.sync_materials"
    bl_label = "Synchronize Material"
    bl_description = "Renumerates the materials of selected terrain chunks and sets their names according to their assigned textures."
    bl_options = {"UNDO"}    
    def execute(self, context):
        rename()
        return {"FINISHED"}


class ResetUVMapping(bpy.types.Operator):
    bl_idname = "import_bw.reset_uv_main"
    bl_label = "Reset Main UV"
    bl_description = "Resets the main UV map so that each tile stretches exactly from one corner of the texture to the other."
    bl_options = {"UNDO"}    
    def execute(self, context):
        reset_uv_selected_objects(main_uv=True, detail_uv=False)
        return {"FINISHED"}

class ResetUVMappingDetail(bpy.types.Operator):
    bl_idname = "import_bw.reset_uv_detail"
    bl_label = "Reset Detail UV"
    bl_description = "Resets the detail UV map so that each tile stretches exactly from one corner of the texture to the other."
    bl_options = {"UNDO"}    
    def execute(self, context):
        reset_uv_selected_objects(main_uv=False, detail_uv=True)
        return {"FINISHED"}


def make_operator(name, idname, label, description, method, **kwargs):
    fields = {"bl_idname": idname, "bl_label": label, "bl_description": description, "execute": method}
    for k, v in kwargs.items():
        fields[k] = v
        
    return type(
        name, 
        (bpy.types.Operator, ), 
        fields)


backup_settings_weight = {
    0: None,
    1: None,
    2: None }

backup_settings_color = {
    0: None,
    1: None}


def backup_settings(settings, i, brush):
    settings[i] = (brush.weight, brush.strength, brush.curve_preset, brush.blend)


def restore_settings(settings, i, brush):
    if settings[i] is not None:
        brush.weight, brush.strength, brush.curve_preset, brush.blend = settings[i]
        
        
def switch_to_weight_paint(self, context):
    if bpy.context.mode != "PAINT_WEIGHT":
        bpy.ops.paint.weight_paint_toggle()
        
    backup_settings(
        backup_settings_weight,
        bpy.context.active_object.vertex_groups.active_index, 
        bpy.data.brushes["Paint"])
    
    bpy.context.active_object.vertex_groups.active_index = self.index
    if self.index in (1,2):
        bpy.data.brushes["Paint"].curve_preset = "CONSTANT"
        bpy.data.brushes["Paint"].blend = "MIX"
        bpy.data.brushes["Paint"].strength = 1.0 
    else:
        restore_settings(
            backup_settings_weight,
            bpy.context.active_object.vertex_groups.active_index, 
            bpy.data.brushes["Paint"])
    return {"FINISHED"}


def switch_to_vertex_paint(self, context):
    if bpy.context.mode != "PAINT_VERTEX":
        bpy.ops.paint.vertex_paint_toggle()
    
    backup_settings(
        backup_settings_color,
        bpy.context.active_object.data.color_attributes.active_color_index, 
        bpy.data.brushes["Paint Hard"])
    
    bpy.context.active_object.data.color_attributes.active_color_index = self.index
    
    restore_settings(
        backup_settings_color,
        bpy.context.active_object.data.color_attributes.active_color_index, 
        bpy.data.brushes["Paint Hard"])
    
    return {"FINISHED"}

    

def weight_paint_with_material(self, context):
    if bpy.context.mode != "PAINT_WEIGHT":
        bpy.ops.paint.weight_paint_toggle()
        
    backup_settings(
        backup_settings_weight,
        bpy.context.active_object.vertex_groups.active_index, 
        bpy.data.brushes["Paint"])
    
    bpy.context.active_object.vertex_groups.active_index = 2
    mat_index = bpy.context.object.active_material_index 
    if mat_index == 0:
        raise RuntimeError("Can't paint with Deleted Terrain")
    else:
        bpy.context.scene.tool_settings.unified_paint_settings.weight = (mat_index-1)/100.0
        bpy.data.brushes["Paint"].weight = (mat_index-1)/100.0
        bpy.data.brushes["Paint"].curve_preset = "CONSTANT"
        bpy.data.brushes["Paint"].blend = "MIX"
        bpy.data.brushes["Paint"].strength = 1.0 
    return {"FINISHED"}


def duplicate_selected_material(self, context):
    active_obj = bpy.context.active_object
    active_index = bpy.context.object.active_material_index 
    bpy.ops.object.material_slot_add()
    active_obj.material_slots[-1].material = active_obj.material_slots[active_index].material.copy()
    #bpy.ops.material.new()
    rename()
    
    return {"FINISHED"}


def try_get(f, ind):
    try:
        val = f(ind)
    except RuntimeError:
        return None 
    else:
        return val
    

def delete_material_index(index):
    bpy.context.object.active_material_index = index
    active_index = index
    bpy.ops.object.material_slot_remove()
    active_obj = bpy.context.active_object
    get_mat_index = active_obj.vertex_groups["Material"].weight

    replace = {}
    
    for i in range(len(active_obj.data.vertices)):
        material = try_get(get_mat_index, i)
        
        
        if material is not None:
            index = int(round(material*100))
            if index >= active_index - 1:
                if index not in replace:
                    replace[index] = [i]
                else:
                    replace[index].append(i)
                    
    add_mat = active_obj.vertex_groups["Material"].add
    for mat, indices in replace.items():
        print("moving", mat)
        add_mat(indices, (mat-1)/100.0, "REPLACE")
    
    
def delete_selected_material(self, context):
    active_obj = bpy.context.active_object
    active_index = bpy.context.object.active_material_index 
    print("===")
    
    if active_index == 0:
        raise RuntimeError("Cannot delete DELETED TERRAIN")
    print(active_index)
    delete_material_index(active_index)
    rename()
    
    return {"FINISHED"}


def get_index_for_mat(slots, mat):
    for i, slot in enumerate(slots):
        if slot.material == mat:
            return i
    
    return None 


def delete_unused_materials(self, context):
    active_obj = bpy.context.active_object
    all_materials = [i for i in range(len(active_obj.material_slots))]
    all_materials.pop(0)
    get_mat_index = active_obj.vertex_groups["Material"].weight
    for i in range(len(active_obj.data.vertices)):
        material = try_get(get_mat_index, i)
        
        if material is not None:
            index = int(round(material*100))
            if index+1 in all_materials:
                all_materials.remove(index+1)
    materials = [bpy.context.object.material_slots[i].material for i in all_materials]
    
    for mat in materials:
        i = get_index_for_mat(active_obj.material_slots, mat)
        assert i is not None
        delete_material_index(i)
    
    rename()
    return {"FINISHED"}
    


def switch_to_normal(self, context):
    if bpy.context.mode != "PAINT_VERTEX":
        bpy.ops.paint.vertex_paint_toggle()
    bpy.ops.paint.vertex_paint_toggle()
    return {"FINISHED"}


def add_material(self, context):
    active_obj = bpy.context.active_object
    
    print(context.scene.addon_image_holder_1)
    print(context.scene.addon_image_holder_2)
    if context.scene.addon_image_holder_1 is None:
        raise RuntimeError("Please choose a main texture!")
    if context.scene.addon_image_holder_2 is None:
        raise RuntimeError("Please choose a detail texture!")
    tex1_name = context.scene.addon_image_holder_1.name.split(".")[0].lower()
    if len(tex1_name) >= 16:
        raise RuntimeError("Main Texture name too long: Needs to be <=16 symbols long.")
    
    
    tex2_name = context.scene.addon_image_holder_2.name.split(".")[0].lower()
    if len(tex2_name) >= 16:
        raise RuntimeError("Detail Texture name too long: Needs to be <=16 symbols long.")
    

    for mat in active_obj.data.materials:
        try:
            name1 = mat.node_tree.nodes["texturemain"].image.name.split(".")[0].lower()
            name2 = mat.node_tree.nodes["texturedetail"].image.name.split(".")[0].lower()
        except KeyError:
            pass 
        else:
            if tex1_name == name1 and tex2_name == name2:
                raise RuntimeError(f"Material with this texture combination exists: {mat.name}")
    
    
    i = len(active_obj.data.materials)
    mat_name = f"Mat{i:02}_{tex1_name}_{tex2_name}"
    
    material = create_terrain_material(
        mat_name,
        context.scene.addon_image_holder_1,
        context.scene.addon_image_holder_2
    )
    material["Value 1"] = 0
    material["Value 2"] = 0
    material["Value 3"] = 0
    material["Value 4"] = 0
    active_obj.data.materials.append(material)
    return {"FINISHED"}

def set_material_texture(self, context):
    pass
    

def sort_materials(self, context):
    active_obj = bpy.context.active_object
    materials = [slot.material for slot in active_obj.material_slots[1:]]
    sorted_materials = [mat for mat in materials]
    get_matname = lambda x: x.image.name.split(".")[0].lower()
    sorted_materials.sort(key=lambda mat:get_matname(mat.node_tree.nodes["texturemain"]) +get_matname(mat.node_tree.nodes["texturedetail"]))
    remap = {}
    for i, mat in enumerate(materials):
        remap[i] = sorted_materials.index(mat)
    for i, slot in enumerate(active_obj.material_slots):
        if i > 0:
            matindex = i - 1 
            mat = sorted_materials[matindex]
            slot.material = mat 
    
    active_obj = bpy.context.active_object
    get_mat_index = active_obj.vertex_groups["Material"].weight

    replace = {}
    
    for i in range(len(active_obj.data.vertices)):
        material = try_get(get_mat_index, i)
        
        
        if material is not None:
            index = int(round(material*100))
            if index not in replace:
                replace[index] = [i]
            else:
                replace[index].append(i)
                    
    add_mat = active_obj.vertex_groups["Material"].add
    for mat, indices in replace.items():
        print("moving", mat, "to", remap[mat])
        add_mat(indices, remap[mat]/100.0, "REPLACE")
    rename()
    
    return {"FINISHED"}


def create_terrain(self, context):
    return {"FINISHED"}


class Operators:
    @staticmethod
    def all():
        for field in dir(Operators):
            if not field.startswith("_") and field != "all":
                yield getattr(Operators, field)
    
    AddTerrainChunk = make_operator(
        "AddTerrainChunk",
        "import_bw.add_terrain", 
        "Create Terrain Object",
        "Creates a 256 by 256 blank terrain object.",
        create_terrain)
    
    SwitchWeightpaintHeight = make_operator(
        "SwitchWeightpaintHeight",
        "import_bw.switch_weightpaint_height", 
        "Switch To Height Paint",
        "Switches to Height Painting mode. A weight of 0.1 equals 51.2 units in height.",
        switch_to_weight_paint,
        index=0)


    SwitchWeightpaintDelete = make_operator(
        "SwitchWeightpaintDelete",
        "import_bw.switch_weightpaint_delete", 
        "Switch To Height Paint",
        "Switches to Deletion Painting mode. A weight of 1.0 deletes chunks, a weight of 0.0 adds chunks.",
        switch_to_weight_paint,
        index=1)


    SwitchWeightpaintMaterial = make_operator(
        "SwitchWeightpaintMaterial",
        "import_bw.switch_weightpaint_material", 
        "Switch To Height Paint",
        ("Switches to Material Painting mode. The first two digits after the dot refer to the number of the material.\n"
        "Example: To paint a material numbered 52, set weight to 0.52.\n"
        "Note: To paint, aim for the bottom left corner of a 4x4 points tile. Falloff->Constant is recommended."),
        switch_to_weight_paint,
        index=2)


    SwitchWeightpaintMaterialSelected = make_operator(
        "SwitchWeightpaintMaterialSelected",
        "import_bw.switch_weightpaint_material_selected", 
        "Paint With Selected Material",
        ("Switches to Material Painting mode using the object's selected material.\n"
        "Use the 'Paint' brush for the material painting index to be set correctly."),
        weight_paint_with_material)
        

    SwitchVertexPaintColor = make_operator(
        "SwitchVertexPaintColor",
        "import_bw.switch_vertex_color", 
        "Switch To Color Paint",
        ("Switches to Vertex Color Paint mode."),
        switch_to_vertex_paint,
        index=1)


    SwitchVertexPaintBlend = make_operator(
        "SwitchVertexPaintBlend",
        "import_bw.switch_vertex_color_blend", 
        "Switch To Blend Paint",
        ("Switches to Vertex Blend Mode. Use Brush Blending mode Add Alpha/Erase Alpha to modify blending between main and detail texture.\n"
        "Erase alpha to make main texture more visible, add alpha to make detail texture more visible."),
        switch_to_vertex_paint,
        index=0)

    SwitchToNormal = make_operator(
        "SwitchToNormal",
        "import_bw.switch_to_normal", 
        "Switch To Object Mode",
        ("Switches to Object Mode"),
        switch_to_normal)


    DuplicateMaterial = make_operator(
        "DuplicateMaterial",
        "import_bw.dupe_mat", 
        "Duplicate Selected Material",
        ("Duplicates the selected material. It will be added at the end of the material list."),
        duplicate_selected_material,
        bl_options = {"UNDO"})
        
        
    DeleteMaterial = make_operator(
        "DeleteMaterial",
        "import_bw.delete_material", 
        "Remove Selected Material",
        ("Remove the selected material and adjusts mesh data so that materials are displayed correctly."),
        delete_selected_material,
        bl_options = {"UNDO"})


    DeleteUnusedMaterials = make_operator(
        "DeleteUnusedMaterials",
        "import_bw.delete_unused_material", 
        "Remove Unused Materials",
        ("Remove all materials from selected terrain chunk that aren't currently used by the chunk."),
        delete_unused_materials,
        bl_options = {"UNDO"})


    AddMaterial = make_operator(
        "AddMaterial",
        "import_bw.add_material", 
        "Add Material",
        ("Add material with specified Main and Detail texture."),
        add_material,
        bl_options = {"UNDO"})
    
    SetMaterialTexture = make_operator(
        "SetMaterialTexture",
        "import_bw.set_material_texture", 
        "Set Material Textures",
        ("Change Main and Detail texture for currently selected material."),
        set_material_texture,
        bl_options = {"UNDO"})
    
    SortMaterials = make_operator(
        "SortMaterials",
        "import_bw.sort_materials", 
        "Sort Materials By Textures",
        ("Sort materials by their main and detail texture names"),
        sort_materials,
        bl_options = {"UNDO"})


class VIEW3D_PT_custom(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BW Terrain"
    bl_label = "Battalion Wars Terrain Tools"
    
    def add_operator(self, row, op):
        row.operator(op.bl_idname, text=op.bl_label)
    
    def draw(self, context):
        row = self.layout.row()
        row.operator("import_bw.sew_terrain", text="Sew Terrain")
        self.layout.separator()
        row = self.layout.row()
        row.operator("import_bw.sync_materials", text="Synchronize Material Names")
        row = self.layout.row()
        self.add_operator(row, Operators.SortMaterials)
        
        
        self.layout.separator()
        row = self.layout.row()
        row.operator("import_bw.reset_uv_main", text="Reset Main UV")
        row = self.layout.row()
        row.operator("import_bw.reset_uv_detail", text="Reset Detail UV")
        self.layout.separator()
        
        row = self.layout.row()
        self.add_operator(row, Operators.SwitchToNormal)
        
        row = self.layout.row()
        row.operator("import_bw.switch_weightpaint_height", text="Switch To Height Paint")
        
        row = self.layout.row()
        row.operator("import_bw.switch_weightpaint_delete", text="Switch To Delete Paint")
        
        row = self.layout.row()
        row.operator("import_bw.switch_weightpaint_material", text="Switch To Material Paint")
        
        row = self.layout.row()
        row.operator("import_bw.switch_weightpaint_material_selected", text="Paint With Selected Material")
        
        self.layout.separator()
        
        row = self.layout.row()
        row.operator("import_bw.switch_vertex_color", text="Switch To Color Paint")
        
        row = self.layout.row()
        row.operator("import_bw.switch_vertex_color_blend", text="Switch To Blend Paint")
        
        self.layout.separator()
        
        row = self.layout.row()
        row.operator("import_bw.dupe_mat", text="Duplicate Selected Material")
        
        row = self.layout.row()
        self.add_operator(row, Operators.DeleteMaterial)
        
        row = self.layout.row()
        self.add_operator(row, Operators.DeleteUnusedMaterials)
        
        self.layout.separator()
        row = self.layout.row()
        row.template_ID(context.scene, "addon_image_holder_1", open="image.open", text="Main Texture")
        row = self.layout.row()
        row.template_ID(context.scene, "addon_image_holder_2", open="image.open", text="Detail Texture")
        row = self.layout.row()
        self.add_operator(row, Operators.AddMaterial)
    
        
        
        
            
        
def register():
    from bpy.utils import register_class, unregister_class
    
    register_class(ImportTerrain)
    register_class(ExportTerrain)
    register_class(MESH_OT_SewTerrain)
    register_class(SynchronizeMaterialNames)
    register_class(ResetUVMapping)
    register_class(ResetUVMappingDetail)
    for op in Operators.all():
        register_class(op)
    """register_class(SwitchWeightpaintHeight)
    register_class(SwitchWeightpaintDelete)
    register_class(SwitchWeightpaintMaterial)
    register_class(SwitchWeightpaintMaterialSelected)
    register_class(SwitchVertexPaintColor)
    register_class(SwitchVertexPaintBlend)
    register_class(DuplicateMaterial)
    register_class(SwitchToNormal)
    register_class(DeleteMaterial)
    register_class(DeleteUnusedMaterials)
    register_class(AddMaterial)"""
    
    bpy.types.Scene.addon_image_holder_1 = bpy.props.PointerProperty(type=bpy.types.Image)
    bpy.types.Scene.addon_image_holder_2 = bpy.props.PointerProperty(type=bpy.types.Image)
    
    register_class(VIEW3D_PT_custom)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_export)


def unregister():
    from bpy.utils import register_class, unregister_class
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_export)
    unregister_class(ImportTerrain)
    unregister_class(ExportTerrain)
    unregister_class(MESH_OT_SewTerrain)
    unregister_class(SynchronizeMaterialNames)
    unregister_class(ResetUVMapping)
    unregister_class(ResetUVMappingDetail)
    for op in Operators.all():
        print("unregistering", op)
        unregister_class(op)
    
    del bpy.types.Scene.addon_image_holder_1
    del bpy.types.Scene.addon_image_holder_2
    
    unregister_class(VIEW3D_PT_custom)
    


def menu_import(self, context):
    self.layout.operator(ImportTerrain.bl_idname, text="Battalion Wars Terrain (.out)")

def menu_export(self, context):
    self.layout.operator(ExportTerrain.bl_idname, text="Battalion Wars Terrain (.out)")


def progress_bar(self, context):
    row = self.layout.row()
    row.progress(
        factor=context.window_manager.progress,
        type="BAR",
        text="Operation in progress..." if context.window_manager.progress < 1 else "Operation Finished !"
    )
    row.scale_x = 2


    
if __name__ == "__main__":
    bw_terrain.Hello()
    #texfolder = r"C:\Users\User\Documents\GitHub\battalion-level-editor\TextureTest\BlenderTerrainTest"
    gamefolder = r"D:\Wii games\BattWars\P-G8WP\files\Data\CompoundFiles"
    terr_path = gamefolder+"\\"+"C1_OnPatrol.out"
    res_path = terr_path.replace(".out", "_Level.res")
    try:
        unregister()
    except Exception as err:
        print(err)
    register()


            
    