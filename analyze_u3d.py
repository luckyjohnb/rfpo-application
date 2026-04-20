"""Analyze U3D file block structure."""
import struct

data = open('test_model.u3d','rb').read()

# File header: magic(4) + profileVersion(2) + declarationType(2) + ...
# Actually ECMA-363 header is: 
# magic(4) + version(4) + profileID(4) + declarationSize(4) + fileSize(8) + encoding(4)
# But this file seems to use a simpler header

# Let me just scan through the block chain starting at offset 24
offset = 24  # skip "U3D\0" + 20 bytes header

block_type_names = {
    0xFFFFFF12: "ModifierChain",
    0xFFFFFF14: "GroupNode", 
    0xFFFFFF15: "ModelNode",
    0xFFFFFF16: "LightNode",
    0xFFFFFF21: "LightResource",
    0xFFFFFF22: "ViewNode",
    0xFFFFFF23: "ViewResource",
    0xFFFFFF24: "LitTextureShader",
    0xFFFFFF25: "MaterialResource",
    0xFFFFFF31: "MeshDeclaration",
    0xFFFFFF3B: "MeshContinuation",
    0xFFFFFF3C: "CLODBaseMeshCont",
    0xFFFFFF41: "ShadingModifier",
    0xFFFFFF45: "CLODMeshDecl",
    0xFFFFFF46: "CLODMeshCont",
}

blocks = []
while offset < len(data) - 12:
    bt = struct.unpack_from('<I', data, offset)[0]
    ds = struct.unpack_from('<I', data, offset+4)[0]
    ms = struct.unpack_from('<I', data, offset+8)[0]
    
    bname = block_type_names.get(bt, f"Unknown")
    
    # Try to read name string from block data
    name = ""
    if ds >= 2:
        try:
            nlen = struct.unpack_from('<H', data, offset+12)[0]
            if 0 < nlen < 100:
                name = data[offset+14:offset+14+nlen].decode('utf-8', errors='replace')
        except:
            pass
    
    blocks.append((offset, bt, ds, ms, bname, name))
    
    next_off = offset + 12 + ds + ms
    if next_off % 4:
        next_off += 4 - (next_off % 4)
    
    # Safety: if next_off doesn't advance or goes past end, break
    if next_off <= offset or next_off > len(data):
        break
    offset = next_off

print(f"File size: {len(data)} bytes")
print(f"Blocks found: {len(blocks)}")
print()
for off, bt, ds, ms, bname, name in blocks:
    print(f"  {off:6d}: {bt:#010x} ({bname:20s})  data={ds:6d}  meta={ms:6d}  name='{name}'")
