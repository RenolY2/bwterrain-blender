from .binaryreader import *
from .structs import *

try:
    from PIL import Image
    has_pil = True 
except ModuleNotFoundError:
    has_pil = False 

@dataclass
class SectionHeader(Struct):
    name: bytes = datatype(identifier)
    size: int = datatype(uint32)


@dataclass 
class TerrainInfo(Struct):
    header: SectionHeader = datatype(obj(SectionHeader), expect=lambda x: x.name == b"TERR")
    chunk_x: int = datatype(uint32)
    chunk_y: int = datatype(uint32)
    unk_count: int = datatype(uint32)
    material_count: int = datatype(uint32)
    
    @classmethod 
    def new(cls):
        header = SectionHeader(b"TERR", 0x10)
        return cls(header, 64, 64, 1, 0)


@dataclass
class Color(Struct):
    r: int = datatype(uint8)
    g: int = datatype(uint8)
    b: int = datatype(uint8)
    a: int = datatype(uint8)
    
    @classmethod 
    def default(cls):
        return cls(255, 255, 255, 255)


@dataclass 
class UVPoint(object):
    x: float  # ushort
    y: float  # ushort

    def to_file(self, f):
        #print(self.x, self.y)
        f.write_format(int(self.x*4096), int(self.y*4096), fmt=">HH")
    
    @classmethod
    def from_file(cls, f):
        x,y = f.read_format(fmt=">HH")
        return cls(x/4096.0, y/4096.0)

    @classmethod
    def default(cls):
        return cls(0.0, 0.0)
    
    
@dataclass
class Tile(Struct):
    heights: int = datatype(uint16be, count=16)
    colors: Color = datatype(obj(Color), count=16)
    surface_coordinates: list = datatype(obj(UVPoint), count=4)
    detail_coordinates: list = datatype(obj(UVPoint), count=16)
    material_index: int = datatype(uint32be)
    
    def get_height(self):
        return min(heights)/16.0
    
    @classmethod
    def default(cls):
        heights = [0 for i in range(16)]
        colors = [Color.default() for i in range(16)]
        surface_coords = [UVPoint.default() for i in range(4)]
        detail_coords = [UVPoint.default() for i in range(16)]
        material_index = 0
        
        return cls(heights, colors, surface_coords, detail_coords, material_index)

@dataclass
class Chunk(Struct):
    tiles: list = datatype(obj(Tile), count=16)
    
    @classmethod
    def default(cls):
        tiles = [Tile.default() for i in range(16)]
        
        return cls(tiles)


class ChunkSection(object):
    def __init__(self):
        self.chunks = []
        
    @classmethod 
    def from_file(cls, f):
        section = cls()
    
        header = f.read_object(SectionHeader)
        assert header.name == b"CHNK"
        assert header.size % (180*16) == 0
        chunk_count = header.size // (180*16) 
        section.chunks = f.read_object(Chunk, count=chunk_count) 

        return section
    
    def to_file(self, f):
        hdr = SectionHeader(b"CHNK", len(self.chunks)*180*16)
        f.write_object(hdr)
        for chunk in self.chunks:
            f.write_object(chunk)
        
        
@dataclass 
class VertexOffset(Struct):
    x: int = datatype(uint16be)
    y: int = datatype(uint16be)


@dataclass 
class TileTransform(Struct):
    header: SectionHeader = datatype(obj(SectionHeader), expect=lambda x: x.name == b"GPNF")
    vertex_offsets: list = datatype(obj(VertexOffset), count=16)
    unk_1: VertexOffset = datatype(obj(VertexOffset))  # Unused?
    unk_2: VertexOffset = datatype(obj(VertexOffset)) # Unused?
    tile_offset: VertexOffset = datatype(obj(VertexOffset)) 
    
    @classmethod
    def default(cls):
        header = SectionHeader(b"GPNF", 0x4C)
        vertex_offsets = [
            VertexOffset(0, 0), VertexOffset(0x55, 0), VertexOffset(0xAA, 0), VertexOffset(0x100, 0),
            VertexOffset(0, 0x55), VertexOffset(0x55, 0x55), VertexOffset(0xAA, 0x55), VertexOffset(0x100, 0x55),
            VertexOffset(0, 0xAA), VertexOffset(0x55, 0xAA), VertexOffset(0xAA, 0xAA), VertexOffset(0x100, 0xAA),
            VertexOffset(0, 0x100), VertexOffset(0x55, 0x100), VertexOffset(0xAA, 0x100), VertexOffset(0x100, 0x100)]
        
        return cls(
            header, 
            vertex_offsets, 
            VertexOffset(0, 0),
            VertexOffset(0x100, 0x100),
            VertexOffset(0x100, 0x100))
    

@dataclass
class ChunkMapEntry(Struct):
    a: int = datatype(uint8)
    b: int = datatype(uint8) 
    index: int = datatype(uint16be) 
    
    def chunk_exists(self):
        return self.b == 1
    
    def set_chunk(self, index):
        self.b = 1 
        self.index = index 
    

class ChunkMap(object):
    def __init__(self):
        self.entries: list[list[ChunkMapEntry]] = [
            [ChunkMapEntry(0, 2, 0xFFFF) for i in range(64)] for j in range(64)
        ]
    
    @classmethod
    def from_file(cls, f):
        section = cls()
        header = f.read_object(SectionHeader)
        assert header.name == b"CMAP"
        assert header.size == 64*64*4
        
        for x in range(64):
            for y in range(64):
                entry = f.read_object(ChunkMapEntry)
                section.entries[x][y] = entry 
        
        return section 
    
    def to_file(self, f):
        hdr = SectionHeader(b"CMAP", 64*64*4)
        f.write_object(hdr)
        for x in range(64):
            for y in range(64):
                f.write_object(self.entries[x][y])
    
@dataclass 
class CollisionMapInfo(Struct):
    version: int = datatype(uint32be, expect=0x66)
    unk_4: int = datatype(uint32be)
    unk_8: int = datatype(uint32be)
    unk_C: int = datatype(uint32be)
    unk_10: int = datatype(uint32be)
    unk_14: int = datatype(uint32be)
    size_x: int = datatype(uint32be)
    size_y: int = datatype(uint32be)
    unk_20: int = datatype(uint32be)
    unk_24: int = datatype(uint32be)
    section1_size: int = datatype(uint32be)
    section2_size: int = datatype(uint32be)
    unk_30: int = datatype(uint32be)
    unk_34: int = datatype(uint32be)


class RepeatingValuesContainer(object):
    def __init__(self):
        self.values = []
    
    def add(self, sequence):
        assert isinstance(sequence, tuple), "Sequence needs to be a tuple"
        
        try:
            index = self.values.index(sequence)
        except ValueError:
            index = len(self.values)
            self.values.append(sequence)
        
        return index
    
    def flatten(self):
        out = []
        for seq in self.values:
            out.extend(seq)
        
        return out


class CollisionMap(object):
    def __init__(self):
        self.info = None 
        self.indices = [] # Section 1
        self.floats = [] # Section 2: Signed16 converted to float by dividing by 16 
        
    @classmethod 
    def from_file(cls, f):
        section = cls() 
        
        colmap = f.read_object(SectionHeader)
        assert colmap.name == b"COLM"
        
        colmapinfo = f.read_object(CollisionMapInfo)
        section.info = colmapinfo 
        section.indices = f.read_uint16_be(count=colmapinfo.section1_size//2)
        section.floats = [f.read_int16_be() / 16.0 for i in range(colmapinfo.section2_size//2)]
            
        return section
    
    def to_file(self, f):
        self.info.section1_size = len(self.indices)*2
        self.info.section2_size = len(self.floats)*2
    
        tmp = BinaryReader()
        tmp.write_object(self.info)
        for index in self.indices:
            tmp.write_uint16_be(index)
        
        for val in self.floats:
            tmp.write_int16_be(int(val*16))
        
        result = tmp.getvalue()
        hdr = SectionHeader(b"COLM", len(result))
        f.write_object(hdr)
        f.write(result)
    
    def save_img(self, outpath):
        if not has_pil:
            raise RuntimeError("Unsupported because PIL is not installed.")
        colmap = self 
        img = Image.new("RGB", (colmap.info.size_x*16, colmap.info.size_y*16))
        for x in range(colmap.info.size_x*16):
            for y in range(colmap.info.size_y*16):
                index = colmap.info.size_x*(y//16) + x//16 
                hi = colmap.indices[index]
                lo = (x & 0xF) | ((y & 0xF) << 4)
                
                float_index = (hi << 8) + lo 
                val = colmap.floats[float_index]
                
                based_val = int(val)
                
                img.putpixel((x, colmap.info.size_y*16-1-y), based_val)
    
        img.save(outpath)
        
    def regenerate_from(self, chunk_map, chunks):
        heights = [[44.0 for y in range(48*16)] for x in range(48*16)]
        for x in range(48*16):
            for y in range(48*16):
                if x % 12 == 0 or y % 12 == 0:
                    heights[x][y] = 0.0
        
        for x in range(64):
            for y in range(64):
                entry = chunk_map.entries[x][y]
                if entry.b == 1:
                    chunk = chunks.chunks[entry.index]
                    for tilex in range(4):
                        for tiley in range(4):
                            tile = chunk.tiles[tilex*4+tiley]
                             
                            for ix in range(3):
                                for iy in range(3):
                                    height = tile.heights[ix*4+iy]/16.0
                                    
                                    total_x = x*12 + tilex*3 + ix 
                                    total_y = y*12 + tiley*3 + iy 
                                    
                                    heights[total_x][total_y] = height 
        
        indices = []
        height_values = RepeatingValuesContainer()
        
        
        for x in range(48):
            for y in range(48):
                values = []
                for ix in range(16):
                    for iy in range(16):
                        values.append(heights[x*16+ix][y*16+iy])
                
                index = height_values.add(tuple(values))
                indices.append(index)
                
        self.indices = indices 
        self.floats = height_values.flatten()
        


@dataclass
class MapMaterial(Struct):
    mat_main: str = datatype(string(16))
    mat_detail: str = datatype(string(16))
    unk_1: int = datatype(uint32)
    unk_2: int = datatype(uint32)
    unk_3: int = datatype(uint32)
    unk_4: int = datatype(uint32)

@dataclass
class UWCTEntry(Struct):
    data: list = datatype(uint32be, count=0xB4//4)

    @classmethod 
    def new(cls):
        return cls(
            (537010178, 537010178, 537010178, 537010178, 
            537010178, 537010178, 537010178, 537010178, 
            16777215, 4281808695, 4281808695, 4281808695, 
            16777215, 4281808695, 4281808695, 4281808695, 
            16777215, 4281808695, 4281808695, 4281808695, 
            16777215, 4281808695, 4281808695, 4281808695, 
            1048576, 1048592, 0, 16, 0, 21765, 43530, 16, 
            1426391040, 1426412805, 1426434570, 1426391056, 
            2852782080, 2852803845, 2852825610, 2852782096, 
            1048576, 1070341, 1092106, 1048592, 0))
            
class UWCTSection(object):
    def __init__(self):
        self.entries = []
    
    @classmethod
    def from_file(cls, f):
        section = cls() 
        
        colmap = f.read_object(SectionHeader)
        assert colmap.name == b"UWCT"
        assert colmap.size % 0xB4 == 0
        
        for i in range(colmap.size // 0xB4):
            entry = f.read_object(UWCTEntry)
            section.entries.append(entry)
        
        return section 
    
    @classmethod 
    def default(cls):
        section = cls()
        for i in range(16):
            section.entries.append(UWCTEntry.new())
        
        return section 
    
    def to_file(self, f):
        hdr = SectionHeader(b"UWCT", len(self.entries)*0xB4)
        f.write_object(hdr)
        for entry in self.entries:
            f.write_object(entry)
        

class MapMaterialSection(object):
    def __init__(self):
        self.materials = []
    
    @classmethod
    def from_file(cls, br):
        material_sec = cls()
        header = br.read_object(SectionHeader)
        assert header.name == b"MATL"
        assert header.size % 48 == 0
        mat_count = header.size//48

        for i in range(mat_count):
            material = br.read_object(MapMaterial)
            material_sec.materials.append(material)
        
        return material_sec
    
    def to_file(self, f):
        size = len(self.materials)*48 
        hdr = SectionHeader(b"MATL", size)
        f.write_object(hdr)
        for mat in self.materials:
            f.write_object(mat)
    
    def count(self):
        return len(self.materials)


class TerrainFile(object):
    def __init__(self):
       pass
    
    def new(cls):
        self = cls()
        self.terrain_info = TerrainInfo.new()
        self.chunks = ChunkSection()
        self.transform = TileTransform.default()
        self.chunkmap = ChunkMap()
        self.uwct = UWCTSection.default()
        self.collmap = CollisionMap()
        self.materials = MapMaterialSection()
        
        return self 
    
    @classmethod
    def from_file(cls, f):
        terrain = cls()
        
        terrain.terrain_info = f.read_object(TerrainInfo)
        terrain.chunks = f.read_object(ChunkSection)
        terrain.transform = f.read_object(TileTransform)
        terrain.chunkmap = f.read_object(ChunkMap)
        terrain.uwct = f.read_object(UWCTSection)
        terrain.collmap = f.read_object(CollisionMap)
        terrain.materials = f.read_object(MapMaterialSection)
        
        for row in terrain.chunkmap.entries:
            for entry in row:
                assert entry.a == 0
                assert entry.b in (1, 2)
        
        terrain.sort_materials()
        
        return terrain 
    
    def to_file(self, f):
        self.terrain_info.material_count = self.materials.count() 
        self.regenerate_collmap()
        self.sort_chunks()
        
        f.write_object(self.terrain_info)
        f.write_object(self.chunks)
        f.write_object(self.transform)
        f.write_object(self.chunkmap)
        f.write_object(self.uwct)
        f.write_object(self.collmap)
        f.write_object(self.materials)
    
    def sort_chunks(self):
        chunks = []
        for cx in range(64):
            for cy in range(64):
                order = cy + cx*64 
                entry = self.chunkmap.entries[cx][cy]
                if entry.chunk_exists():
                    chunk = self.chunks.chunks[entry.index]
                
                    chunks.append((chunk, order, entry))
        
        chunks.sort(key=lambda x: x[1])
        
        for i, v in enumerate(chunks):
            chunk, order, entry = v 
            entry.index = i 
        self.chunks.chunks = [i[0] for i in chunks]
    
    def sort_materials(self):
        materials = [mat for mat in self.materials.materials]
        materials.sort(key=lambda mat: mat.mat_main+mat.mat_detail)
        
        remap = {}
        for i, mat in enumerate(self.materials.materials):
            new_index = materials.index(mat)
            remap[i] = new_index 
        
        for chunk in self.chunks.chunks:
            for tile in chunk.tiles:
                tile.material_index = remap[tile.material_index]
        
        self.materials.materials = materials 
    
    def clear_chunks(self):
        self.chunkmap = ChunkMap()
        self.chunks.chunks = []
    
    def set_chunk_exist_status(self, cx, cy, exist):
        entry = self.chunkmap.entries[cx][cy]
        if exist:
            entry.b = 1 
        else:
            entry.b = 2
    
    def get_chunk(self, cx, cy, create_if_no_exist=False):
        entry = self.chunkmap.entries[cx][cy]
        
        if create_if_no_exist and not entry.chunk_exists():
            chunk = Chunk.default()
            index = len(self.chunks.chunks)
            self.chunks.chunks.append(chunk)
            entry.set_chunk(index)
        
        elif entry.chunk_exists():
            chunk = self.chunks.chunks[entry.index]
        else:
            chunk = None 
        
        return chunk
    
    def regenerate_collmap(self):
        self.collmap.regenerate_from(self.chunkmap, self.chunks)
        

if __name__ == "__main__":
    with open("C1_OnPatrol.out", "rb") as f:
        data = f.read()
    
    br = BinaryReader(data)
    terrain = br.read_object(TerrainFile)
    """terr_hdr = br.read_object(TerrainInfo)
    print(terr_hdr)
    
    chnk = br.read_object(ChunkSection)
    
    hdr = br.read_object(TileTransform)
    cmap = br.read_object(ChunkMap)
    
    uwct_header = br.read_object(SectionHeader)
    br.read(uwct_header.size)
    
    colmap = br.read_object(CollisionMap)
    print(hex(br.tell()))
    print(br.read_object(MapMaterialSection))"""
    for entry in terrain.uwct.entries:
        for i in range(len(entry.data)):
            entry.data[i] = 0
    print(len(terrain.uwct.entries))
    #terrain.uwct.entries = terrain.uwct.entries[0:10]
    for chunk in terrain.chunks.chunks:
        for tile in chunk.tiles:
            for color in tile.colors:
                color.r = 255
                color.b = 128
                color.g = 128
    
    terrain.collmap.save_img("normal.out.png")
    terrain.regenerate_collmap()
    terrain.collmap.save_img("normalNew.out.png")
    
    new = BinaryReader()
    new.write_object(terrain)
    with open(r"D:\Wii games\BattWars\P-G8WP\files\Data\CompoundFiles\C1_OnPatrol.out", "wb") as f:
        f.write(new.getvalue())
    
    