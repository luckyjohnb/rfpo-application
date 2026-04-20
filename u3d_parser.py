"""Parse U3D mesh continuation block and export to STL/OBJ."""
import struct
import sys

def parse_u3d_to_obj(u3d_path, obj_path):
    data = open(u3d_path, 'rb').read()
    
    # Find MeshContinuation block (type 0xFFFFFF3B)
    offset = 0
    mesh_blocks = []
    
    # Skip file header
    ds = struct.unpack_from('<I', data, 4)[0]
    offset = 12 + ds  # past header block
    if offset % 4: offset += 4 - (offset % 4)
    
    while offset < len(data) - 12:
        bt = struct.unpack_from('<I', data, offset)[0]
        ds = struct.unpack_from('<I', data, offset+4)[0]
        ms = struct.unpack_from('<I', data, offset+8)[0]
        
        if bt == 0xFFFFFF3B:  # MeshContinuation
            mesh_blocks.append((offset, ds))
        
        next_off = offset + 12 + ds + ms
        if next_off % 4: next_off += 4 - (next_off % 4)
        if next_off <= offset: break
        offset = next_off
    
    print(f"Found {len(mesh_blocks)} MeshContinuation blocks")
    
    all_positions = []
    all_faces = []
    vert_offset = 0
    
    for block_off, block_size in mesh_blocks:
        bd = data[block_off + 12 : block_off + 12 + block_size]
        bo = 0
        
        # Name (U16 length + string)
        nlen = struct.unpack_from('<H', bd, bo)[0]; bo += 2
        name = bd[bo:bo+nlen].decode('utf-8', errors='replace'); bo += nlen
        
        # Chain index
        chain_idx = struct.unpack_from('<I', bd, bo)[0]; bo += 4
        
        # Face count
        num_faces = struct.unpack_from('<I', bd, bo)[0]; bo += 4
        
        # Position count
        num_positions = struct.unpack_from('<I', bd, bo)[0]; bo += 4
        
        # Normal count  
        num_normals = struct.unpack_from('<I', bd, bo)[0]; bo += 4
        
        # Diffuse color count
        num_diffuse = struct.unpack_from('<I', bd, bo)[0]; bo += 4
        
        # Specular color count
        num_specular = struct.unpack_from('<I', bd, bo)[0]; bo += 4
        
        # Texture coord count
        num_texcoords = struct.unpack_from('<I', bd, bo)[0]; bo += 4
        
        print(f"Mesh '{name}': faces={num_faces}, positions={num_positions}, normals={num_normals}")
        print(f"  diffuse={num_diffuse}, specular={num_specular}, texcoords={num_texcoords}")
        
        # Read positions
        positions = []
        for i in range(num_positions):
            x = struct.unpack_from('<f', bd, bo)[0]; bo += 4
            y = struct.unpack_from('<f', bd, bo)[0]; bo += 4
            z = struct.unpack_from('<f', bd, bo)[0]; bo += 4
            positions.append((x, y, z))
        
        # Read normals
        normals = []
        for i in range(num_normals):
            nx = struct.unpack_from('<f', bd, bo)[0]; bo += 4
            ny = struct.unpack_from('<f', bd, bo)[0]; bo += 4
            nz = struct.unpack_from('<f', bd, bo)[0]; bo += 4
            normals.append((nx, ny, nz))
        
        # Read diffuse colors (RGBA float = 16 bytes each)
        for i in range(num_diffuse):
            bo += 16
        
        # Read specular colors (RGBA float = 16 bytes each)
        for i in range(num_specular):
            bo += 16
        
        # Read texture coords (4 floats = 16 bytes each? or 2 floats = 8 bytes?)
        # ECMA-363 says texture coords are I32 dimension + dimension * F32
        # But for HARU, let's check...
        for i in range(num_texcoords):
            bo += 8  # U, V (2 x F32)
        
        # Read faces
        # Each face: U32 shadingID + 3 * (U32 posIdx + U32 normIdx [+ optional texIdx])
        faces = []
        face_read_ok = True
        for i in range(num_faces):
            if bo + 4 > len(bd):
                print(f"  Ran out of data at face {i}/{num_faces}, offset {bo}/{len(bd)}")
                face_read_ok = False
                break
            
            shading_id = struct.unpack_from('<I', bd, bo)[0]; bo += 4
            
            face_verts = []
            for v in range(3):
                if bo + 8 > len(bd):
                    face_read_ok = False
                    break
                pos_idx = struct.unpack_from('<I', bd, bo)[0]; bo += 4
                norm_idx = struct.unpack_from('<I', bd, bo)[0]; bo += 4
                # Check if there are tex coord indices too
                if num_texcoords > 0:
                    if bo + 4 <= len(bd):
                        tex_idx = struct.unpack_from('<I', bd, bo)[0]; bo += 4
                face_verts.append(pos_idx)
            
            if not face_read_ok:
                break
            faces.append(tuple(face_verts))
        
        if not face_read_ok:
            print(f"  WARNING: Face parsing had issues, got {len(faces)}/{num_faces}")
            # Try without tex coord indices
            if num_texcoords > 0 and len(faces) < num_faces // 2:
                print("  Retrying without tex coord indices in faces...")
                bo2 = bo  # Reset doesn't work easily, let's try from scratch
                # Re-read from after tex coords
                bo2 = 0
                nlen2 = struct.unpack_from('<H', bd, bo2)[0]; bo2 += 2 + nlen2
                bo2 += 4  # chain_idx
                bo2 += 4 * 7  # counts
                bo2 += num_positions * 12  # positions
                bo2 += num_normals * 12  # normals
                bo2 += num_diffuse * 16  # diffuse
                bo2 += num_specular * 16  # specular
                bo2 += num_texcoords * 8  # texcoords
                
                faces2 = []
                for i in range(num_faces):
                    if bo2 + 4 > len(bd):
                        break
                    shading_id = struct.unpack_from('<I', bd, bo2)[0]; bo2 += 4
                    fv = []
                    ok = True
                    for v in range(3):
                        if bo2 + 8 > len(bd):
                            ok = False; break
                        pi = struct.unpack_from('<I', bd, bo2)[0]; bo2 += 4
                        ni = struct.unpack_from('<I', bd, bo2)[0]; bo2 += 4
                        fv.append(pi)
                    if not ok: break
                    faces2.append(tuple(fv))
                
                if len(faces2) > len(faces):
                    print(f"  Without tex indices: got {len(faces2)} faces - using these")
                    faces = faces2
        
        print(f"  Parsed: {len(positions)} positions, {len(normals)} normals, {len(faces)} faces")
        
        # Store with vertex offset for merging
        all_positions.extend(positions)
        for f in faces:
            all_faces.append((f[0] + vert_offset, f[1] + vert_offset, f[2] + vert_offset))
        vert_offset += len(positions)
    
    if not all_positions:
        print("No geometry found!")
        return False
    
    # Export OBJ
    with open(obj_path, 'w') as f:
        f.write("# Converted from U3D\n")
        for v in all_positions:
            f.write(f"v {v[0]} {v[1]} {v[2]}\n")
        for face in all_faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")
    
    print(f"\nExported: {len(all_positions)} vertices, {len(all_faces)} faces -> {obj_path}")
    
    # Also export STL
    stl_path = obj_path.replace('.obj', '.stl')
    with open(stl_path, 'wb') as f:
        f.write(b'\x00' * 80)
        f.write(struct.pack('<I', len(all_faces)))
        for face in all_faces:
            v0 = all_positions[face[0]]
            v1 = all_positions[face[1]]
            v2 = all_positions[face[2]]
            # Normal
            e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
            e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
            n = (e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2], e1[0]*e2[1]-e1[1]*e2[0])
            l = (n[0]**2+n[1]**2+n[2]**2)**0.5
            if l > 0: n = (n[0]/l, n[1]/l, n[2]/l)
            f.write(struct.pack('<fff', *n))
            f.write(struct.pack('<fff', *v0))
            f.write(struct.pack('<fff', *v1))
            f.write(struct.pack('<fff', *v2))
            f.write(struct.pack('<H', 0))
    
    print(f"Exported: {len(all_faces)} triangles -> {stl_path}")
    return True

if __name__ == '__main__':
    u3d = sys.argv[1] if len(sys.argv) > 1 else 'test_model.u3d'
    obj = sys.argv[2] if len(sys.argv) > 2 else 'test_model.obj'
    parse_u3d_to_obj(u3d, obj)
