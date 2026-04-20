"""Extract mesh data from U3D and export as JSON for three.js viewer.

Uses a custom ECMA-363 parser for the vertex/normal data.
Face data uses CLOD arithmetic coding which we can't decode without
a full U3D reference implementation, so we export just the point cloud.
"""
import struct
import json

data = open('test_model.u3d', 'rb').read()

# MeshContinuation block at offset 1516, data size 129868
bd = data[1516 + 12 : 1516 + 12 + 129868]

bo = 0
# Name
nlen = struct.unpack_from('<H', bd, bo)[0]; bo += 2
name = bd[bo:bo+nlen].decode('utf-8', errors='replace'); bo += nlen

# Chain index
chain_idx = struct.unpack_from('<I', bd, bo)[0]; bo += 4

# Counts
num_faces = struct.unpack_from('<I', bd, bo)[0]; bo += 4
num_positions = struct.unpack_from('<I', bd, bo)[0]; bo += 4
num_normals = struct.unpack_from('<I', bd, bo)[0]; bo += 4
num_diffuse = struct.unpack_from('<I', bd, bo)[0]; bo += 4
num_specular = struct.unpack_from('<I', bd, bo)[0]; bo += 4
num_texcoords = struct.unpack_from('<I', bd, bo)[0]; bo += 4

print(f"Mesh: '{name}'")
print(f"Faces: {num_faces}, Positions: {num_positions}, Normals: {num_normals}")

# Read positions
positions = []
for i in range(num_positions):
    x = struct.unpack_from('<f', bd, bo)[0]; bo += 4
    y = struct.unpack_from('<f', bd, bo)[0]; bo += 4
    z = struct.unpack_from('<f', bd, bo)[0]; bo += 4
    positions.append([round(x, 4), round(y, 4), round(z, 4)])

# Read normals
normals = []
for i in range(num_normals):
    x = struct.unpack_from('<f', bd, bo)[0]; bo += 4
    y = struct.unpack_from('<f', bd, bo)[0]; bo += 4
    z = struct.unpack_from('<f', bd, bo)[0]; bo += 4
    normals.append([round(x, 4), round(y, 4), round(z, 4)])

# Export as JSON
mesh_data = {
    "name": name,
    "numFaces": num_faces,
    "numPositions": num_positions,
    "numNormals": num_normals,
    "positions": positions,
    "normals": normals[:num_positions],  # Trim normals to match positions for per-vertex
    "bounds": {
        "minX": min(p[0] for p in positions),
        "maxX": max(p[0] for p in positions),
        "minY": min(p[1] for p in positions),
        "maxY": max(p[1] for p in positions),
        "minZ": min(p[2] for p in positions),
        "maxZ": max(p[2] for p in positions),
    }
}

with open('test_model.json', 'w') as f:
    json.dump(mesh_data, f)

print(f"Exported test_model.json ({len(positions)} positions, {len(normals)} normals)")
print(f"Bounds: X[{mesh_data['bounds']['minX']:.0f}, {mesh_data['bounds']['maxX']:.0f}]"
      f" Y[{mesh_data['bounds']['minY']:.0f}, {mesh_data['bounds']['maxY']:.0f}]"
      f" Z[{mesh_data['bounds']['minZ']:.0f}, {mesh_data['bounds']['maxZ']:.0f}]")
print(f"File size: {len(json.dumps(mesh_data))} bytes")
