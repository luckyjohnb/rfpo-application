"""Convert U3D to OBJ using assimp's C API via ctypes directly."""
import ctypes
import ctypes.wintypes
import struct
import os

# Load assimp DLL
dll = ctypes.CDLL('./assimp-vc143-mt.dll')

# Define structures
class aiVector3D(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]

class aiFace(ctypes.Structure):
    _fields_ = [("mNumIndices", ctypes.c_uint), ("mIndices", ctypes.POINTER(ctypes.c_uint))]

class aiString(ctypes.Structure):
    _fields_ = [("length", ctypes.c_uint32), ("data", ctypes.c_char * 1024)]

class aiMesh(ctypes.Structure):
    _fields_ = [
        ("mPrimitiveTypes", ctypes.c_uint),
        ("mNumVertices", ctypes.c_uint),
        ("mNumFaces", ctypes.c_uint),
        ("mVertices", ctypes.POINTER(aiVector3D)),
        ("mNormals", ctypes.POINTER(aiVector3D)),
        ("mTangents", ctypes.POINTER(aiVector3D)),
        ("mBitangents", ctypes.POINTER(aiVector3D)),
        ("mColors", ctypes.POINTER(ctypes.c_void_p) * 8),
        ("mTextureCoords", ctypes.POINTER(ctypes.c_void_p) * 8),
        ("mNumUVComponents", ctypes.c_uint * 8),
        ("mFaces", ctypes.POINTER(aiFace)),
        ("mNumBones", ctypes.c_uint),
        ("mBones", ctypes.c_void_p),
        ("mMaterialIndex", ctypes.c_uint),
        ("mName", aiString),
    ]

class aiScene(ctypes.Structure):
    _fields_ = [
        ("mFlags", ctypes.c_uint),
        ("mRootNode", ctypes.c_void_p),
        ("mNumMeshes", ctypes.c_uint),
        ("mMeshes", ctypes.POINTER(ctypes.POINTER(aiMesh))),
        ("mNumMaterials", ctypes.c_uint),
        ("mMaterials", ctypes.c_void_p),
        ("mNumAnimations", ctypes.c_uint),
        ("mAnimations", ctypes.c_void_p),
        ("mNumTextures", ctypes.c_uint),
        ("mTextures", ctypes.c_void_p),
        ("mNumLights", ctypes.c_uint),
        ("mLights", ctypes.c_void_p),
        ("mNumCameras", ctypes.c_uint),
        ("mCameras", ctypes.c_void_p),
    ]

# Set up function signatures
dll.aiImportFile.restype = ctypes.POINTER(aiScene)
dll.aiImportFile.argtypes = [ctypes.c_char_p, ctypes.c_uint]
dll.aiReleaseImport.argtypes = [ctypes.POINTER(aiScene)]
dll.aiGetErrorString.restype = ctypes.c_char_p

# Import the U3D file
# Flags: aiProcess_Triangulate=0x8 | aiProcess_JoinIdenticalVertices=0x2
scene = dll.aiImportFile(b'test_model.u3d', 0x8 | 0x2)

if not scene:
    err = dll.aiGetErrorString()
    print(f"Error: {err.decode()}")
    exit(1)

s = scene.contents
print(f"Scene: {s.mNumMeshes} meshes, {s.mNumMaterials} materials")

# Export to OBJ
with open('test_model.obj', 'w') as f:
    f.write("# U3D to OBJ via assimp ctypes\n")
    vertex_offset = 1
    
    for i in range(s.mNumMeshes):
        mesh = s.mMeshes[i].contents
        name = mesh.mName.data[:mesh.mName.length].decode('utf-8', errors='replace')
        print(f"  Mesh {i}: '{name}', {mesh.mNumVertices} verts, {mesh.mNumFaces} faces")
        
        f.write(f"\n# Mesh: {name}\n")
        f.write(f"o {name}\n")
        
        # Write vertices
        for v in range(mesh.mNumVertices):
            vert = mesh.mVertices[v]
            f.write(f"v {vert.x} {vert.y} {vert.z}\n")
        
        # Write normals if available
        has_normals = bool(mesh.mNormals)
        if has_normals:
            for v in range(mesh.mNumVertices):
                norm = mesh.mNormals[v]
                f.write(f"vn {norm.x} {norm.y} {norm.z}\n")
        
        # Write faces
        for fi in range(mesh.mNumFaces):
            face = mesh.mFaces[fi]
            if face.mNumIndices == 3:
                i0 = face.mIndices[0] + vertex_offset
                i1 = face.mIndices[1] + vertex_offset
                i2 = face.mIndices[2] + vertex_offset
                if has_normals:
                    f.write(f"f {i0}//{i0} {i1}//{i1} {i2}//{i2}\n")
                else:
                    f.write(f"f {i0} {i1} {i2}\n")
        
        vertex_offset += mesh.mNumVertices

print(f"Exported test_model.obj ({os.path.getsize('test_model.obj')} bytes)")

dll.aiReleaseImport(scene)
