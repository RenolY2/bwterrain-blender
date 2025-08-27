import dataclasses 
import struct
from functools import partial
from io import BytesIO


class BinaryReader(BytesIO):
    def read_uint32(self, count=None):
        if count is None:
            data = self.read(4)
            return struct.unpack("I", data)[0]
        else:
            return [self.read_uint32() for i in range(count)]
    
    def read_uint32_be(self, count=None):
        if count is None:
            data = self.read(4)
            return struct.unpack(">I", data)[0]
        else:
            return [self.read_uint32() for i in range(count)]
    
    def read_uint16(self, count=None, endian=""):
        if count is None:
            data = self.read(2)
            return struct.unpack("H", data)[0]
        else:
            return [self.read_uint16() for i in range(count)]
    
    def read_uint16_be(self, count=None, endian=""):
        if count is None:
            data = self.read(2)
            return struct.unpack(">H", data)[0]
        else:
            return [self.read_uint16_be() for i in range(count)]
    
    def read_int16_be(self, count=None, endian=""):
        if count is None:
            data = self.read(2)
            return struct.unpack(">h", data)[0]
        else:
            return [self.read_uint16() for i in range(count)]
    
    def read_uint8(self):
        data = self.read(1)
        return struct.unpack("B", data)[0]
    
    def read_float(self, endian=""):
        data = self.read(4)
        return struct.unpack("f", data)[0]
    
    def read_float_be(self, endian=""):
        data = self.read(4)
        return struct.unpack(">f", data)[0]
    
    def read_format(self, single=False, fmt=None):
        size = struct.calcsize(fmt)
        data = self.read(size)
        if single:
            return struct.unpack(fmt, data)[0]
        else:
            return struct.unpack(fmt, data)
    
    def read_object(self, obj=None, count=None):
        if count is None:
            return obj.from_file(self)
        else:
            return [obj.from_file(self) for i in range(count)]
    
    def _write_val(self, fmt, value):
        if isinstance(value, list):
            for val in value:
                self.write(struct.pack(fmt, val))
        else:
            self.write(struct.pack(fmt, value))
    
    def write_uint32(self, value):
        self._write_val("I", value)
        
    def write_uint16(self, value):
        self._write_val("H", value)
        
    def write_uint8(self, value):
        self._write_val("B", value)
        
    def write_float(self, value):
        self._write_val("f", value)
    
    # Big Endian
    def write_uint32_be(self, value):
        self._write_val(">I", value)
        
    def write_uint16_be(self, value):
        self._write_val(">H", value)
    
    def write_int16_be(self, value):
        self._write_val(">h", value)
        
    def write_float_be(self, value):
        self._write_val(">f", value)
    
    def write_format(self, *values, fmt=None):
        self.write(struct.pack(fmt, *values))
    
    def write_object(self, obj=None):
        if isinstance(obj, list):
            for obj_ in obj:
                obj_.to_file(self)
        else:
            obj.to_file(self) 
    
    def read_terminated_string(self, size=None):
        data = self.read(size)
        zero = data.find(b"\x00")
        return data[:zero]

    def write_terminated_string(self, value, size=None):
        assert len(value) <= size 
        self.write(value)
        self.write(b"\x00"*(size-len(value)))
    
    def read_identifier(self):
        val = self.read(4)
        return val[::-1]
    
    def write_identifier(self, value):
        assert len(value) == 4
        self.write(value[::-1])


def datatype(func, count=None, countvar=None, expect=None):
    assert len(func) == 2, "Func parameter for datatype is wrong"
    
    # We allow functions and direct comparisons to values as expectations
    if not callable(expect) and expect:
        expectation = expect 
        #expect = lambda x: print(x, expect); x == expect 
        def expect(x):
            print(x, expectation)
            return x == expectation
        
        
    return dataclasses.field(metadata={"reader": func, "count": count, "countvar": countvar, "expect": expect})
    

uint32 = (BinaryReader.read_uint32, BinaryReader.write_uint32)
uint16 = (BinaryReader.read_uint16, BinaryReader.write_uint16)
uint32be = (BinaryReader.read_uint32_be, BinaryReader.write_uint32_be)
uint16be = (BinaryReader.read_uint16_be, BinaryReader.write_uint16_be)
uint8 = (BinaryReader.read_uint8, BinaryReader.write_uint8)
float32 = (BinaryReader.read_float, BinaryReader.write_float)
float3be = (BinaryReader.read_float_be, BinaryReader.write_float_be)
identifier = (BinaryReader.read_identifier, BinaryReader.write_identifier)
fmt = lambda x: (partial(BinaryReader.read_format, fmt=x), partial(BinaryReader.write_format, fmt=x))
fmt_single = lambda x: (partial(BinaryReader.read_format, fmt=x, single=True), partial(BinaryReader.write_format, fmt=x))
obj = lambda x: (partial(BinaryReader.read_object, obj=x), BinaryReader.write_object)#partial(BinaryReader.write_object, obj=x) )
string = lambda x: fmt_single("{}s".format(x))



fixed_string = lambda x: (partial(BinaryReader.read_terminated_string, size=x), partial(BinaryReader.write_terminated_string, size=x))