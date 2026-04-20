"""Deeper analysis of U3D file - check actual ECMA-363 header format."""
import struct

data = open('test_model.u3d', 'rb') .read()

print(f"File size: {len(data)} bytes")
print()

# ECMA-363 Section 9.2 - File Structure
# File Header Block:
#   Block Type: U32 = 0x00443355 ("U3D\0" little-endian)
#   Data Size: U32
#   Meta Data Size: U32

# Let's check: the first 4 bytes ARE U3D\0, but are they also the block type?
# In ECMA-363, the very first block IS the file header block with type 0x00443355

# Wait - "U3D\0" = 55 33 44 00 = 0x00443355 in little-endian!
# So the first block IS the header block.

# Block header: type(4) + dataSize(4) + metaDataSize(4)
block_type = struct.unpack_from('<I', data, 0)[0]
data_size = struct.unpack_from('<I', data, 4)[0]  
meta_size = struct.unpack_from('<I', data, 8)[0]

print(f"Block 0: type={block_type:#010x}, data_size={data_size}, meta_size={meta_size}")

# File Header block data (ECMA-363 9.2):
#   I16 versionMajor
#   I16 versionMinor  
#   U32 profileIdentifier
#   U32 declarationSize
#   U64 fileSize
#   U32 characterEncoding

bo = 12  # after block header
ver_major = struct.unpack_from('<h', data, bo)[0]; bo += 2
ver_minor = struct.unpack_from('<h', data, bo)[0]; bo += 2
profile = struct.unpack_from('<I', data, bo)[0]; bo += 4
decl_size = struct.unpack_from('<I', data, bo)[0]; bo += 4
file_size = struct.unpack_from('<Q', data, bo)[0]; bo += 8
char_enc = struct.unpack_from('<I', data, bo)[0]; bo += 4

print(f"  Version: {ver_major}.{ver_minor}")
print(f"  Profile: {profile:#x}")
print(f"  Declaration size: {decl_size}")
print(f"  File size: {file_size}")
print(f"  Character encoding: {char_enc}")

# Now the data_size tells us how big the header data is
# After that: meta data (if any)
next_block = 12 + data_size + meta_size
# Pad to 4-byte alignment
if next_block % 4:
    next_block += 4 - (next_block % 4)

print(f"\nNext block starts at offset: {next_block}")
print()

# Now parse remaining blocks
block_type_names = {
    0x00443355: "FileHeader",
    0xFFFFFF12: "ModifierChain",
    0xFFFFFF14: "GroupNode",
    0xFFFFFF15: "ModelNode", 
    0xFFFFFF16: "LightNode",
    0xFFFFFF21: "LightResource",
    0xFFFFFF22: "ViewNode",
    0xFFFFFF23: "ViewResource",
    0xFFFFFF24: "LitTextureShader",
    0xFFFFFF25: "MaterialResource",
    0xFFFFFF26: "TextureResource",
    0xFFFFFF31: "MeshDeclaration",
    0xFFFFFF36: "PointSetDecl",
    0xFFFFFF37: "LineSetDecl",
    0xFFFFFF3B: "MeshContinuation",
    0xFFFFFF3C: "CLODBaseMeshCont",
    0xFFFFFF3E: "PointSetCont",
    0xFFFFFF3F: "LineSetCont",
    0xFFFFFF41: "ShadingModifier",
    0xFFFFFF42: "CLODModifier",
    0xFFFFFF45: "CLODMeshDecl",
    0xFFFFFF46: "CLODMeshCont",
}

offset = next_block
block_num = 1
while offset < len(data) - 12:
    bt = struct.unpack_from('<I', data, offset)[0]
    ds = struct.unpack_from('<I', data, offset+4)[0]
    ms = struct.unpack_from('<I', data, offset+8)[0]
    
    bname = block_type_names.get(bt, f"Unknown({bt:#010x})")
    
    # Read name if present
    name = ""
    bd_start = offset + 12
    if ds >= 2 and bd_start + 2 <= len(data):
        nlen = struct.unpack_from('<H', data, bd_start)[0]
        if 0 < nlen < 200 and bd_start + 2 + nlen <= len(data):
            name = data[bd_start+2:bd_start+2+nlen].decode('utf-8', errors='replace')
    
    print(f"Block {block_num:3d} @ {offset:6d}: {bname:22s}  data={ds:6d}  meta={ms:6d}  name='{name}'")
    
    next_off = offset + 12 + ds + ms
    if next_off % 4:
        next_off += 4 - (next_off % 4)
    
    if next_off <= offset:
        print("  ERROR: block doesn't advance, stopping")
        break
    if next_off > len(data) + 4:
        print(f"  WARNING: next offset {next_off} > file size {len(data)}")
        break
    
    offset = next_off
    block_num += 1
    
    if block_num > 200:
        print("... (stopping at 200 blocks)")
        break

print(f"\nTotal blocks parsed: {block_num}")
