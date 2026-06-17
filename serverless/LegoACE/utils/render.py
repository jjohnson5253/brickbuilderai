import trimesh
import numpy as np
from PIL import Image
import os
from utils.utils import normalize_mesh, look_at
os.environ["PYOPENGL_PLATFORM"] = "osmesa"
import pyrender

def render_glb_normal(glb_path, model_mat=None, camera_position=np.array([1.0, 1.0, 1.0])):
    mesh = trimesh.load(glb_path, force='mesh')
    if mesh.is_empty:
        return Image.new("RGB", (512, 512), (255, 255, 255))
    mesh = normalize_mesh(mesh)
    scene = pyrender.Scene()
    mesh_node = pyrender.Mesh.from_trimesh(mesh, poses=model_mat)
    scene.add(mesh_node)


    camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)

    look_at_mat = look_at(camera_position, np.array([0.0, 0.0, 0.0]))
    camera_pose = np.linalg.inv(look_at_mat)
    scene.add(camera, pose=camera_pose)

    # Set up the renderer
    renderer = pyrender.OffscreenRenderer(viewport_width=512, viewport_height=512)
    renderer._renderer._program_cache = pyrender.shader_program.ShaderProgramCache(shader_dir="./utils/shader")
    # Render the global space normal map
    color, _ = renderer.render(scene)
    renderer.delete()

    return Image.fromarray(color)

def render_mesh(mesh):
    scene = pyrender.Scene()
    mesh_node = pyrender.Mesh.from_trimesh(mesh, smooth=True)
    scene.add(mesh_node)


    camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)

    look_at_mat = look_at(np.array([1.0, 1.0, 1.0]), np.array([0.0, 0.0, 0.0]))
    camera_pose = np.linalg.inv(look_at_mat)

    scene.add(camera, pose=camera_pose)


    renderer = pyrender.OffscreenRenderer(viewport_width=512, viewport_height=512)
    renderer._renderer._program_cache = pyrender.shader_program.ShaderProgramCache(shader_dir="./utils/shader")

    color, depth = renderer.render(scene)
    return Image.fromarray(color)