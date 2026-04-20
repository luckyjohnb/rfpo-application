"""Parse U3D mesh - try multiple face format interpretations."""
import struct

data = open('test_model.u3d', 'rb').read()

# Jump directly to MeshContinuation block at offset 1516
# (found from analyze_u3d_v2.py: Block 14 @ 1516, data=129868)
bd = data[1516 + 12 : 1516 + 12 + 129868]

bo = 0
# Name
nlen = struct.unpack_from('<H', bd, bo)[0]; bo += 2
name = bd[bo:bo+nlen].decode('utf-8', errors='replace'); bo += nlen
print(f"Name: '{name}'")

# Chain index
chain_idx = struct.unpack_from('<I', bd, bo)[0]; bo += 4
print(f"Chain index: {chain_idx}")

# Counts
num_faces = struct.unpack_from('<I', bd, bo)[0]; bo += 4
num_positions = struct.unpack_from('<I', bd, bo)[0]; bo += 4
num_normals = struct.unpack_from('<I', bd, bo)[0]; bo += 4
num_diffuse = struct.unpack_from('<I', bd, bo)[0]; bo += 4
num_specular = struct.unpack_from('<I', bd, bo)[0]; bo += 4
num_texcoords = struct.unpack_from('<I', bd, bo)[0]; bo += 4

print(f"Faces: {num_faces}")
print(f"Positions: {num_positions}")
print(f"Normals: {num_normals}")
print(f"Diffuse: {num_diffuse}")
print(f"Specular: {num_specular}")
print(f"TexCoords: {num_texcoords}")

positions_start = bo
# Read positions
positions = []
for i in range(num_positions):
    x = struct.unpack_from('<f', bd, bo)[0]; bo += 4
    y = struct.unpack_from('<f', bd, bo)[0]; bo += 4
    z = struct.unpack_from('<f', bd, bo)[0]; bo += 4
    positions.append((x, y, z))

print(f"\nFirst 3 positions: {positions[:3]}")
print(f"Position range X: {min(p[0] for p in positions):.2f} to {max(p[0] for p in positions):.2f}")
print(f"Position range Y: {min(p[1] for p in positions):.2f} to {max(p[1] for p in positions):.2f}")
print(f"Position range Z: {min(p[2] for p in positions):.2f} to {max(p[2] for p in positions):.2f}")

normals_start = bo
# Read normals (12 bytes each)
bo += num_normals * 12
print(f"Skipped {num_normals} normals ({num_normals * 12} bytes)")

# Skip diffuse (16 bytes each)
bo += num_diffuse * 16
# Skip specular (16 bytes each)  
bo += num_specular * 16

# Texture coords - try different sizes
print(f"\nBefore texcoords: offset {bo}")
# Try 8 bytes per texcoord (U, V as F32)
texcoord_pos_8 = bo + num_texcoords * 8
# Try 16 bytes (U, V, S, T or something)
texcoord_pos_16 = bo + num_texcoords * 16
# Try 12 bytes
texcoord_pos_12 = bo + num_texcoords * 12

print(f"After texcoords (8B each): {texcoord_pos_8}")
print(f"After texcoords (12B each): {texcoord_pos_12}")
print(f"After texcoords (16B each): {texcoord_pos_16}")

# Try each possibility and see which gives valid face data
remaining = len(bd) - texcoord_pos_8
bytes_per_face_needed = remaining / num_faces if num_faces > 0 else 0
print(f"\nRemaining after 8B texcoords: {remaining} bytes")
print(f"Bytes per face (if 8B tc): {bytes_per_face_needed:.1f}")

remaining = len(bd) - texcoord_pos_12
bytes_per_face_needed = remaining / num_faces if num_faces > 0 else 0
print(f"Remaining after 12B texcoords: {remaining} bytes")
print(f"Bytes per face (if 12B tc): {bytes_per_face_needed:.1f}")

remaining = len(bd) - texcoord_pos_16
bytes_per_face_needed = remaining / num_faces if num_faces > 0 else 0
print(f"Remaining after 16B texcoords: {remaining} bytes")
print(f"Bytes per face (if 16B tc): {bytes_per_face_needed:.1f}")

# Face structure options:
# Option A: shadingId(4) + 3 * (posIdx(4) + normIdx(4)) = 28 bytes
# Option B: shadingId(4) + 3 * (posIdx(4) + normIdx(4) + texIdx(4)) = 40 bytes
# Option C: shadingId(4) + 3 * (posIdx(4) + normIdx(4) + diffIdx(4) + texIdx(4)) = 52 bytes

print(f"\nExpected face sizes:")
print(f"  28 bytes/face (no tex idx): {28 * num_faces} bytes needed")
print(f"  40 bytes/face (with tex idx): {40 * num_faces} bytes needed")
print(f"  52 bytes/face (with diffuse+tex): {52 * num_faces} bytes needed")

# Try with 8 bytes per texcoord and see which face format works
for tc_size in [8, 16, 12]:
    faces_start = texcoord_pos_8 if tc_size == 8 else (texcoord_pos_16 if tc_size == 16 else texcoord_pos_12)
    for face_size_name, per_vert in [("pos+norm", 8), ("pos+norm+tex", 12), ("pos+norm+diff+tex", 16)]:
        face_bytes = 4 + 3 * per_vert  # shading_id + 3 verts
        total_needed = face_bytes * num_faces
        remaining = len(bd) - faces_start
        
        if abs(remaining - total_needed) < 20:  # allow small padding
            print(f"\n*** MATCH: tc={tc_size}B, face={face_size_name} ({face_bytes}B) ***")
            print(f"    faces_start={faces_start}, needed={total_needed}, available={remaining}")
            
            # Try parsing first 5 faces
            bo2 = faces_start
            for i in range(min(5, num_faces)):
                sid = struct.unpack_from('<I', bd, bo2)[0]; bo2 += 4
                verts = []
                for v in range(3):
                    vals = []
                    for _ in range(per_vert // 4):
                        val = struct.unpack_from('<I', bd, bo2)[0]; bo2 += 4
                        vals.append(val)
                    verts.append(vals)
                print(f"    Face {i}: shading={sid}, verts={verts}")
