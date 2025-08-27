import xml.etree.ElementTree as etree

class SimpleLevelXML(object):
    def __init__(self, xmlfile):
        self._tree = etree.parse(xmlfile)
        self._root = self._tree.getroot()
        self.textures = []
        self.ids = []
        
        for obj in self._root:
            if obj.tag == "Object" and obj.attrib["type"] == "cTextureResource":
                objid = obj.attrib["id"]
                texname = self.getTexName(obj)
                if texname is not None:
                    self.textures.append(texname.lower())
                self.ids.append(int(objid))
    
    def getTexName(self, tex):
        for attr_node in tex:
            if attr_node.tag == "Attribute" and attr_node.attrib["name"] == "mName":
                return attr_node[0].text
    
    def add_texture(self, name, texid):
        xml = etree.fromstring(f"""
<Object type="cTextureResource" id="{texid}">
    <Attribute name="mName" type="cFxString8" elements="1">
        <Item>{name}</Item>
    </Attribute>
</Object>
""")         
        self._root.append(xml)
    
    def write(self, f):
        f.write(b"<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
        self._tree.write(f, encoding="utf-8", short_empty_elements=False)
        
if __name__ == "__main__":
    with open("C1_OnPatrol_Level.xml", "rb") as f:
        levelxml = SimpleLevelXML(f)
    
    with open("C1_OnPatrol_Level_preload.xml", "r") as f:
        preloadxml = SimpleLevelXML(f)
    
    cummulative_ids = levelxml.ids + preloadxml.ids 
    texnames = levelxml.textures 
    def choose_unique_id(num, ids):
        while num in ids:
            num += 7
        
        return num 
    
    for texname in ("tex1", "tex2", "tex3", "WF_SRATO01"):
        if texname.lower() not in texnames:
            newid = choose_unique_id(1100000000, cummulative_ids)
            cummulative_ids.append(newid)
            levelxml.add_texture(texname, newid)
            print("added", texname, "as", newid)
        else:
            print("skipped", texname)
        
    with open("C1_OnPatrol_LevelNew.xml", "wb") as f:
        levelxml.write(f)