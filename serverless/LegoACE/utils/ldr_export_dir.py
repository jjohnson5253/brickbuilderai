import bpy
import sys
from pathlib import Path
def ldr_to_glb_single(filepath, target_path):
    bpy.ops.import_scene.importldraw(filepath=filepath)
    bpy.data.objects.remove(bpy.data.objects["LegoGroundPlane"], do_unlink=True)
    bpy.ops.export_scene.gltf(filepath=target_path, export_format="GLB", export_draco_mesh_compression_enable=False)
    # bpy.ops.wm.obj_export(filepath=target_path[:-4]+".obj")
    bpy.ops.wm.read_homefile()
    

def ldr_to_glb_dir(ldr_dir, glb_dir):
    ldr_dir = Path(ldr_dir)
    glb_dir = Path(glb_dir)

    for ldr in ldr_dir.glob("*.ldr"):
        glb = glb_dir / (ldr.stem + ".glb")
        ldr_to_glb_single(str(ldr), str(glb))



args = sys.argv[sys.argv.index("--") + 1:]
ldr_file_dir = args[0]
output_dir = args[1]

ldr_to_glb_dir(ldr_file_dir, output_dir)