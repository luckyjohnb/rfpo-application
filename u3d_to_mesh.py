"""
Parse U3D (ECMA-363) file and extract mesh geometry, export to STL.
Supports the basic mesh continuation block format used by HARU PDF library.
"""
import struct
import sys
import os

def read_u16(data, offset):
    return struct.unpack_from('<H', data, offset)[0], offset + 2

def read_u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0], offset + 4

def read_f32(data, offset):
    return struct.unpack_from('<f', data, offset)[0], offset + 4

def read_string(data, offset):
    length, offset = read_u16(data, offset)
    s = data[offset:offset+length].decode('utf-8', errors='replace')
    return s, offset + length

def parse_u3d(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    
    # File header
    magic = data[0:4]
    if magic != b'U3D\x00':
        print(f"Not a valid U3D file (magic: {magic})")
        return None
    
    # Parse header block
    # Header: magic(4) + majorVersion(2) + minorVersion(2) + profileId(4) + 
    #         declarationSize(4) + fileSize(8) + characterEncoding(4)
    major, _ = read_u16(data, 4)
    minor, _ = read_u16(data, 6)
    profile, _ = read_u32(data, 8)
    decl_size, _ = read_u32(data, 12)
    file_size = struct.unpack_from('<Q', data, 16)[0]
    
    print(f"U3D v{major}.{minor}, profile={profile:#x}, declared={decl_size}, file_size={file_size}")
    
    # Parse blocks
    offset = 24  # after file header
    
    # Padding to 4-byte alignment
    if offset % 4 != 0:
        offset += 4 - (offset % 4)
    
    meshes = {}  # name -> {positions, normals, faces}
    mesh_decls = {}
    
    while offset < len(data) - 8:
        # Block header: blockType(4) + dataSize(4) + metaDataSize(4)
        if offset + 12 > len(data):
            break
            
        block_type, _ = read_u32(data, offset)
        data_size, _ = read_u32(data, offset + 4)
        meta_size, _ = read_u32(data, offset + 8)
        
        block_data_start = offset + 12
        block_data = data[block_data_start:block_data_start + data_size]
        
        # Block types from ECMA-363
        block_names = {
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
            0xFFFFFF36: "PointSetDeclaration",
            0xFFFFFF37: "LineSetDeclaration",
            0xFFFFFF3B: "MeshContinuation",
            0xFFFFFF3C: "CLODBaseMeshContinuation",
            0xFFFFFF3E: "PointSetContinuation",
            0xFFFFFF3F: "LineSetContinuation",
            0xFFFFFF41: "ShadingModifier",
            0xFFFFFF42: "CLODModifier",
            0xFFFFFF45: "CLOD Mesh Declaration",
            0xFFFFFF46: "CLOD Mesh Continuation",
        }
        
        bname = block_names.get(block_type, f"Unknown({block_type:#010x})")
        print(f"  Block: {bname} at {offset}, data={data_size}, meta={meta_size}")
        
        try:
            if block_type == 0xFFFFFF31:  # Mesh Declaration
                bo = 0
                name, bo = read_string(block_data, bo)
                chain_idx, bo = read_u32(block_data, bo)
                # Max mesh description
                max_resolution, bo = read_u32(block_data, bo)  # face count (max)
                # Mesh attributes
                num_positions, bo = read_u32(block_data, bo)
                num_normals, bo = read_u32(block_data, bo)
                num_diffuse_colors, bo = read_u32(block_data, bo)
                num_specular_colors, bo = read_u32(block_data, bo)
                num_tex_coords, bo = read_u32(block_data, bo)
                
                # Number of shading descriptions
                num_shading, bo = read_u32(block_data, bo)
                
                print(f"    Mesh '{name}': faces={max_resolution}, pos={num_positions}, norms={num_normals}")
                mesh_decls[name] = {
                    'max_faces': max_resolution,
                    'num_positions': num_positions,
                    'num_normals': num_normals,
                    'num_shading': num_shading,
                }
                meshes[name] = {'positions': [], 'normals': [], 'faces': []}
            
            elif block_type == 0xFFFFFF45:  # CLOD Mesh Declaration
                bo = 0
                name, bo = read_string(block_data, bo)
                chain_idx, bo = read_u32(block_data, bo)
                # Min/Max mesh description
                # Min resolution attributes
                min_resolution, bo = read_u32(block_data, bo)
                # Max resolution attributes  
                max_resolution, bo = read_u32(block_data, bo)
                
                # Position/normal/etc counts
                num_positions, bo = read_u32(block_data, bo)
                num_normals, bo = read_u32(block_data, bo)
                num_diffuse, bo = read_u32(block_data, bo)
                num_specular, bo = read_u32(block_data, bo)
                num_tex, bo = read_u32(block_data, bo)
                num_shading, bo = read_u32(block_data, bo)
                
                print(f"    CLOD Mesh '{name}': min={min_resolution}, max={max_resolution}, pos={num_positions}, norms={num_normals}")
                mesh_decls[name] = {
                    'min_faces': min_resolution,
                    'max_faces': max_resolution,
                    'num_positions': num_positions,
                    'num_normals': num_normals,
                    'num_shading': num_shading,
                    'is_clod': True,
                }
                meshes[name] = {'positions': [], 'normals': [], 'faces': []}
            
            elif block_type in (0xFFFFFF3B, 0xFFFFFF3C, 0xFFFFFF46):  # Mesh/CLOD Continuation
                bo = 0
                name, bo = read_string(block_data, bo)
                chain_idx, bo = read_u32(block_data, bo)
                
                # Base mesh data
                num_faces, bo = read_u32(block_data, bo)
                num_positions, bo = read_u32(block_data, bo)
                num_normals, bo = read_u32(block_data, bo)
                num_diffuse, bo = read_u32(block_data, bo)
                num_specular, bo = read_u32(block_data, bo)
                num_tex, bo = read_u32(block_data, bo)
                
                print(f"    Continuation '{name}': faces={num_faces}, pos={num_positions}, norms={num_normals}")
                
                if name not in meshes:
                    meshes[name] = {'positions': [], 'normals': [], 'faces': []}
                
                # Read positions
                positions = []
                for i in range(num_positions):
                    x, bo = read_f32(block_data, bo)
                    y, bo = read_f32(block_data, bo)
                    z, bo = read_f32(block_data, bo)
                    positions.append((x, y, z))
                
                # Read normals
                normals = []
                for i in range(num_normals):
                    nx, bo = read_f32(block_data, bo)
                    ny, bo = read_f32(block_data, bo)
                    nz, bo = read_f32(block_data, bo)
                    normals.append((nx, ny, nz))
                
                # Skip diffuse colors
                for i in range(num_diffuse):
                    bo += 16  # RGBA float
                
                # Skip specular colors
                for i in range(num_specular):
                    bo += 16  # RGBA float
                
                # Skip tex coords
                for i in range(num_tex):
                    bo += 16  # 4 floats
                
                # Read faces
                faces = []
                for i in range(num_faces):
                    if bo + 12 > len(block_data):
                        print(f"    WARNING: ran out of data at face {i}/{num_faces}")
                        break
                    shading_id, bo = read_u32(block_data, bo)
                    # Each face has 3 vertices, each with position/normal indices
                    face_verts = []
                    for v in range(3):
                        pos_idx, bo = read_u32(block_data, bo)
                        norm_idx, bo = read_u32(block_data, bo)
                        # Skip optional diffuse/specular/tex indices based on shading desc
                        face_verts.append(pos_idx)
                    faces.append(tuple(face_verts))
                
                meshes[name]['positions'] = positions
                meshes[name]['normals'] = normals
                meshes[name]['faces'] = faces
                
                print(f"    Parsed: {len(positions)} positions, {len(normals)} normals, {len(faces)} faces")
                
        except Exception as e:
            print(f"    Parse error: {e}")
        
        # Move to next block (data + metadata + padding)
        next_offset = block_data_start + data_size + meta_size
        if next_offset % 4 != 0:
            next_offset += 4 - (next_offset % 4)
        offset = next_offset
    
    return meshes

def export_stl(meshes, output_path):
    """Export meshes to binary STL."""
    all_triangles = []
    
    for name, mesh in meshes.items():
        positions = mesh['positions']
        faces = mesh['faces']
        normals = mesh.get('normals', [])
        
        if not positions or not faces:
            continue
        
        for face in faces:
            if len(face) < 3:
                continue
            try:
                v0 = positions[face[0]]
                v1 = positions[face[1]]
                v2 = positions[face[2]]
            except IndexError:
                continue
            
            # Calculate face normal
            e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
            e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
            n = (
                e1[1]*e2[2] - e1[2]*e2[1],
                e1[2]*e2[0] - e1[0]*e2[2],
                e1[0]*e2[1] - e1[1]*e2[0]
            )
            length = (n[0]**2 + n[1]**2 + n[2]**2) ** 0.5
            if length > 0:
                n = (n[0]/length, n[1]/length, n[2]/length)
            
            all_triangles.append((n, v0, v1, v2))
    
    if not all_triangles:
        print("No triangles to export!")
        return False
    
    # Write binary STL
    with open(output_path, 'wb') as f:
        # 80-byte header
        f.write(b'\x00' * 80)
        # Triangle count
        f.write(struct.pack('<I', len(all_triangles)))
        # Triangles
        for normal, v0, v1, v2 in all_triangles:
            f.write(struct.pack('<fff', *normal))
            f.write(struct.pack('<fff', *v0))
            f.write(struct.pack('<fff', *v1))
            f.write(struct.pack('<fff', *v2))
            f.write(struct.pack('<H', 0))  # attribute byte count
    
    print(f"Exported {len(all_triangles)} triangles to {output_path}")
    return True

def export_obj(meshes, output_path):
    """Export meshes to OBJ format (simpler, good for debugging)."""
    vertex_offset = 1  # OBJ is 1-indexed
    
    with open(output_path, 'w') as f:
        f.write(f"# Exported from U3D\n")
        
        for name, mesh in meshes.items():
            positions = mesh['positions']
            faces = mesh['faces']
            
            if not positions or not faces:
                continue
            
            f.write(f"o {name}\n")
            
            for v in positions:
                f.write(f"v {v[0]} {v[1]} {v[2]}\n")
            
            for face in faces:
                if len(face) >= 3:
                    f.write(f"f {face[0]+vertex_offset} {face[1]+vertex_offset} {face[2]+vertex_offset}\n")
            
            vertex_offset += len(positions)
    
    total_verts = sum(len(m['positions']) for m in meshes.values())
    total_faces = sum(len(m['faces']) for m in meshes.values())
    print(f"Exported {total_verts} vertices, {total_faces} faces to {output_path}")
    return True

if __name__ == '__main__':
    u3d_file = sys.argv[1] if len(sys.argv) > 1 else 'test_model.u3d'
    
    meshes = parse_u3d(u3d_file)
    
    if meshes:
        total_v = sum(len(m['positions']) for m in meshes.values())
        total_f = sum(len(m['faces']) for m in meshes.values())
        print(f"\nTotal: {len(meshes)} meshes, {total_v} vertices, {total_f} faces")
        
        if total_v > 0:
            base = os.path.splitext(u3d_file)[0]
            export_stl(meshes, base + '.stl')
            export_obj(meshes, base + '.obj')
        else:
            print("No geometry extracted - U3D format may use a different block structure")
