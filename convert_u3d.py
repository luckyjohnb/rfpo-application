"""Convert U3D to OBJ/STL using pyassimp with native DLL."""
import os
import sys

# Must set before importing pyassimp
dll_path = os.path.join(os.getcwd(), 'assimp-bin', 'Release', 'assimp-vc143-mt.dll')
os.environ['ASSIMP_LIBRARY_PATH'] = dll_path
print(f"DLL: {dll_path}")
print(f"Exists: {os.path.exists(dll_path)}")

import pyassimp

scene = pyassimp.load('test_model.u3d')
print(f'Meshes: {len(scene.meshes)}')

for m in scene.meshes:
    print(f'  Vertices: {len(m.vertices)}, Faces: {len(m.faces)}')

# Export to OBJ
with open('test_model.obj', 'w') as f:
    f.write("# U3D to OBJ via assimp\n")
    vi = 1
    for m in scene.meshes:
        for v in m.vertices:
            f.write(f"v {v[0]} {v[1]} {v[2]}\n")
        if hasattr(m, 'normals') and len(m.normals) > 0:
            for n in m.normals:
                f.write(f"vn {n[0]} {n[1]} {n[2]}\n")
        for face in m.faces:
            indices = ' '.join(f"{idx + vi}//{idx + vi}" for idx in face.indices)
            f.write(f"f {indices}\n")
        vi += len(m.vertices)

print("Exported test_model.obj")

# Also try STL export
try:
    pyassimp.export(scene, 'test_model.stl', 'stl')
    print("Exported test_model.stl")
except Exception as e:
    print(f"STL export failed: {e}")

pyassimp.release(scene)
