import dataclasses 
import struct
from io import BytesIO
from functools import partial
from dataclasses import dataclass, fields
from .binaryreader import BinaryReader, datatype, uint32, uint16, uint8, float32, fmt, obj, string, fixed_string
    
class Struct:
    @classmethod
    def from_file(cls, f: BinaryReader):
        values = []
        look_back = {}
        
        for field in fields(cls):
            if "reader" in field.metadata:
                reader, _ = field.metadata["reader"]
                if field.metadata.get("count") is not None:
                    count = field.metadata["count"]
                    value = [reader(f) for i in range(count)]
                elif field.metadata.get("countvar") is not None:
                    count = look_back[field.metadata["countvar"]]
                    value = [reader(f) for i in range(count)]
                else:
                    value = reader(f)
                
                if field.metadata.get("expect") is not None:
                    func = field.metadata.get("expect")
                    if not func(value):
                        raise AssertionError(f"Assertion failed for field {field.name} in struct {cls}")
                
                values.append(value)
                look_back[field.name] = value 
                
        return cls(*values)
        
    def to_file(self, f:BinaryReader):
        countsrc = {}
        
        for field in fields(self):
            if "countvar" in field.metadata:
                countvar = field.metadata["countvar"]
                countsrc[countvar] = field.name 
        
        for field in fields(self):
            if "reader" in field.metadata:
                _, writer = field.metadata["reader"]
                
                if field.name in countsrc:
                    value = len(getattr(self, countsrc[field.name]))
                else:
                    value = getattr(self, field.name)
                
                writer(f, value)
    
    def to_json(self):
        result = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, list):
                out = []
                for val in value:
                    if hasattr(val, "to_json"):
                        out.append(val.to_json())
                    else:
                        out.append(val)
                value = out 
                
            if hasattr(value, "to_json"):
                value = value.to_json()
            
            
            result[field.name] = value 
        
        return result 
    
    @classmethod
    def from_json(cls, data):
        if not isinstance(data, list):
            values = []
            for field in fields(cls):
                if hasattr(field.type, "from_json"):    
                    from_json = field.type.from_json
                    value = from_json(data[field.name])
                else:
                    value = data[field.name]
                
                values.append(value)
            
            return cls(*values)
            
        else:
            objs = []
            for dat in data:
                values = []
                for field in fields(cls):
                    if hasattr(field.type, "from_json"):    
                        from_json = field.type.from_json
                        value = from_json(dat[field.name])
                    else:
                        value = dat[field.name]
                    
                    values.append(value)
            
                objs.append(cls(*values))
            
            return objs
        
        
        
        
@dataclass
class Vector3(Struct):
    x: float = datatype(float32)
    y: float = datatype(float32) 
    z: float = datatype(float32)
    
    @classmethod 
    def default(cls):
        return cls(0.0, 0.0, 0.0)


@dataclass
class Vector2(Struct):
    x: float = datatype(float32)
    y: float = datatype(float32) 
    
    @classmethod 
    def default(cls):
        return cls(0.0, 0.0)

@dataclass
class Vector4(Vector3):
    w: float = datatype(float32)


@dataclass
class Matrix4x4(Struct):
    row1: Vector4 = datatype(obj(Vector4))
    row2: Vector4 = datatype(obj(Vector4))
    row3: Vector4 = datatype(obj(Vector4))
    row4: Vector4 = datatype(obj(Vector4))
    

        
@dataclass 
class WorldVertex(Struct):
    pos: Vector3 = datatype(obj(Vector3))
    normal: Vector3 = datatype(obj(Vector3))
    color: Vector3 = datatype(uint32)
    uv: Vector3 = datatype(obj(Vector2))


class TextureEntry(object):
    def __init__(self, name):
        self.name = name 
    
    @classmethod
    def from_file(cls, f):
        bytename = f.read(0x20)
        assert len(bytename) == 0x20, "Name isn't 0x20 bytes"
        decoded = bytename.strip(b"\x00").decode("ascii")
        
        return cls(decoded)

@dataclass
class RenderLight(Struct):
    flags: int               = datatype(uint32) 
    light_type: int          = datatype(uint32) 
    style: int               = datatype(uint32)  
    color: Vector3           = datatype(obj(Vector3))  
    intensity: float         = datatype(float32)   
    base_intensity: float    = datatype(float32)    
    direction: Vector3       = datatype(obj(Vector3))  
    pos: Vector3             = datatype(obj(Vector3))   
    angle1: float            = datatype(float32)    
    angle2: float            = datatype(float32)    
    radius: float            = datatype(float32)    
    falloff: float           = datatype(float32)    


@dataclass
class Plane(Struct):
    norm: Vector3 = datatype(obj(Vector3))
    dist: float = datatype(float32)


@dataclass
class Group(Struct):
    shader_index: int = datatype(uint32)
    index_offset: int = datatype(uint32)
    vertex_offset: int = datatype(uint32)
    strip_indices_count: int = datatype(uint16)
    list_indices_count: int = datatype(uint16)
    vertices_count: int = datatype(uint32)
    flags: int = datatype(uint16)
    vertex_pool: int = datatype(uint8)
    bound_min: Vector3 = datatype(obj(Vector3))
    bound_max: Vector3 = datatype(obj(Vector3))


@dataclass
class Portal(Struct):
    normal: Vector3 = datatype(obj(Vector3))
    val1: int = datatype(uint32)
    val2: int = datatype(uint32)
    vtx1: Vector3 = datatype(obj(Vector3))
    vtx2: Vector3 = datatype(obj(Vector3))
    vtx3: Vector3 = datatype(obj(Vector3))
    vtx4: Vector3 = datatype(obj(Vector3))


@dataclass
class Bound3D(Struct):
    min: Vector3 = datatype(obj(Vector3))
    max: Vector3 = datatype(obj(Vector3))


@dataclass
class SoundType(Struct):
    end_id: int = datatype(uint32)
    sound_type: int = datatype(uint16)
    padding: int = datatype(uint16)
    

@dataclass
class MoppCode(Struct):
    unk1: int = datatype(uint32)
    unk2: int = datatype(uint32)
    unk3: int = datatype(uint32)
    unk4: int = datatype(uint32)
    unk5: int = datatype(uint32)


@dataclass
class ThingFrame(Struct):
    orientation: Vector3 = datatype(obj(Vector3))
    position: Vector3 = datatype(obj(Vector3))
    flags: int = datatype(uint16)
    padding: int = datatype(uint16)


@dataclass
class PlayerStartFile(Struct):
    sector_id: int = datatype(uint32)
    matrix_1: Vector3 = datatype(obj(Vector3))
    matrix_2: Vector3 = datatype(obj(Vector3))
    matrix_3: Vector3 = datatype(obj(Vector3))
    matrix_4: Vector3 = datatype(obj(Vector3))
    number: int = datatype(uint32)
    order: int = datatype(uint32)


@dataclass
class BinaryData(Struct):
    val: int = datatype(uint8, count=0x20)


MOD_FORMATS = {
    0: fixed_string(0x20),
    1: obj(Vector3),
    2: obj(Vector3),
    3: uint32,
    4: fixed_string(0x20),
    10: fixed_string(0x20),
    0xB: uint32,
    0xC: uint32,
    0xD: fixed_string(0x20),
    0xE: uint32,
    0xF: fixed_string(0x20), # Script name
    0x10: string(0x20), # Is this used?
    0x11: float32,
    0x12: float32,
    0x13: float32, 
    0x14: uint32, # Actor type
    0x15: uint32,
    0x16: uint32,
    0x19: float32,
    0x1A: float32,
    0x28: uint32,
    0x29: float32,
    0x2A: float32,
    0x2B: fixed_string(0x20),
    0x2C: uint32,
    0x2D: uint32, 
    0x2E: fixed_string(0x20),
    0x2F: fixed_string(0x20),
    0x30: uint32,
    0x31: uint32,
    0x32: float32,
    0x33: uint32,
    0x34: uint32,
    0x35: obj(Vector3),
    0x37: float32,
    0x39: obj(Vector3),
    0x3E: uint32, 
    0x3F: uint32,
    0x40: fixed_string(0x20),
    0x41: float32,
    0x42: fixed_string(0x20),
    0x43: uint32,
    0x4C: fixed_string(0x20),
    0x4D: float32,
    0x4E: float32,
    0x4F: float32,
    0x50: float32,
    0x51: float32,
    0x52: float32,
    0x54: float32,
    0x55: uint32,
    0x56: float32,
    0x89: float32,
    0x8A: float32,
    0x8B: float32,
    0x8C: float32,
    0x8E: float32,
    0x8F: float32,
    0x97: float32,
    0x98: fixed_string(0x20),
    0x9A: fixed_string(0x20),
    0xA1: fixed_string(0x20),
    0xA2: fixed_string(0x20),
    0xA3: fixed_string(0x20),
    0xA4: fixed_string(0x20),
    0xA5: uint32,
    0xA6: fixed_string(0x20),
    0xA8: fixed_string(0x20),
    0xA9: uint32, 
    0xAA: float32, 
    0xAB: uint32, 
    0xAC: fixed_string(0x20),
    0xAD: fixed_string(0x20),
    0xAE: float32, 
    0xAF: obj(Vector3),
    0xB0: uint32,
    0xB1: fixed_string(0x20),
    0xB2: fixed_string(0x20),
    0xB3: float32,
    0xB4: uint32,
    0xB5: uint32,
    0xB6: fixed_string(0x20),
    0xB7: uint32, 
    0xB8: float32,
    0xB9: float32
}


@dataclass
class Modifier(Struct):
    id: int = datatype(uint32)
    data: bytes = datatype(string(0x20))
   
    def resolve_modifier(self):
        if self.id not in MOD_FORMATS:
            reader, _ = obj(BinaryData)
        else:
            reader, _ = MOD_FORMATS[self.id]
        
        self.value = reader(BytesIO(self.data))
    
    def to_file(self, f):
        if self.id not in MOD_FORMATS:
            _, writer = obj(BinaryData)
        else:
            _, writer = MOD_FORMATS[self.id]
        f.write_uint32(self.id)
        start = f.tell()
        writer(f, self.value)
        diff = f.tell()-start 
        f.write(b"\x00"*(0x20-diff))
    
    @classmethod
    def from_file(cls, *args, **kwargs):
        obj = super().from_file(*args, **kwargs)
        obj.resolve_modifier()
        
        return obj 
    
    @classmethod
    def from_json(cls, data):
        id = attr[data["attribute"]]
        value = data["value"]
        if isinstance(value, str):
            value = bytes(value, encoding="ascii")
        elif isinstance(value, dict):
            x, y, z = value["x"], value["y"], value["z"]
            value = Vector3(x, y, z)
        tmp = BinaryReader()
        if id not in MOD_FORMATS:
            _, writer = string(0x20)
        else:
            _, writer = MOD_FORMATS[id]
        
        writer(tmp, value)
        tmp.write(b"\x00"*(0x20-tmp.tell()))
        
        modifier = cls(id, tmp.getvalue())
        modifier.value = value 
        
        return modifier
    
    def to_json(self):
        if hasattr(self.value, "to_json"):
            value = self.value.to_json()
        else:
            value = self.value 
        
        if isinstance(value, bytes):
            value = str(value, encoding="ascii")
            
        result = {
            "attribute": attr[self.id],
            "value": value
        }
        
        return result

@dataclass 
class VtxGroupInfo(Struct):
    vertex_type: int = datatype(uint8)
    padding1: int = datatype(uint8)
    padding2: int = datatype(uint16)
    vertex_count: int = datatype(uint32)
    

@dataclass 
class ModelFile(Struct):
    version: int = datatype(uint32)
    shader_count: int = datatype(uint8)
    bone_count: int = datatype(uint8)
    vertex_group_count: int = datatype(uint8)
    mesh_group_count: int = datatype(uint8)
    flags: int = datatype(uint32)
    bound: Bound3D = datatype(obj(Bound3D))
    group: VtxGroupInfo = datatype(obj(VtxGroupInfo), count=4)
    index_count: int = datatype(uint32)
    lod_start: int = datatype(uint32, count=4)
    lod_count: int = datatype(uint8)
    padding1: int = datatype(uint8)
    padding2: int = datatype(uint16)


@dataclass 
class CameraFrameData(Struct):
    frame_type: int = datatype(uint32)
    flags: int = datatype(uint32)
    fov: float = datatype(float32)
    position: Vector3 = datatype(obj(Vector3))
    focus_position: Vector3 = datatype(obj(Vector3))
    factors: float = datatype(float32, count=3*3)
    
    
@dataclass 
class InterestSpot(Struct):
    sector_union: int = datatype(uint32)
    padding: int = datatype(string(0xC))
    matrix: Matrix4x4 = datatype(obj(Matrix4x4))
    id: int = datatype(uint32)
    radius: float = datatype(float32)
    flags: int = datatype(uint32)
    dot: float = datatype(float32)

@dataclass
class MiscLevelData(Struct):
    music_track: str = datatype(string(0x20))
    ambient_track: str = datatype(string(0x20))
    sound_effects: int = datatype(uint32)
    music_volume: int = datatype(uint32)
    ambient_volume: int = datatype(uint32)
    eax_effect: int = datatype(uint32)
    fog_mode: int = datatype(uint32)
    fog_color: int = datatype(obj(Vector3))
    fog_dist1: float = datatype(float32)
    fog_dist2: float = datatype(float32)
    zclip_distance: float = datatype(float32)
    effects_flags: int = datatype(uint32)
    sky_model: str = datatype(string(0x20))
    sky_animation: str = datatype(string(0x20))