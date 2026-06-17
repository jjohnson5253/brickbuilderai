import numpy as np


def normalize_mesh(mesh):
    """Center a trimesh mesh at the origin and scale its longest side to 1."""
    bbox_min = mesh.vertices.min(axis=0)
    bbox_max = mesh.vertices.max(axis=0)
    bbox_center = (bbox_min + bbox_max) / 2.0
    mesh.vertices -= bbox_center

    bbox_size = bbox_max - bbox_min
    scale_factor = 1.0 / np.max(bbox_size)
    mesh.vertices *= scale_factor
    return mesh


def look_at(camera_position, target, up=np.array([0.0, 1.0, 0.0])):
    """Compute a world-to-camera view matrix using the OpenGL convention."""
    z_axis = camera_position - target
    z_axis = z_axis / np.linalg.norm(z_axis)
    x_axis = np.cross(up, z_axis)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    R = np.array([x_axis, y_axis, z_axis])
    t = -R @ camera_position
    view_matrix = np.eye(4)
    view_matrix[:3, :3] = R
    view_matrix[:3, 3] = t
    return view_matrix


def rotation_matrices_y():
    """Four 4x4 homogeneous matrices for 0/90/180/270-degree rotations about the Y axis."""
    return [
        np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]),
        np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]]),
        np.array([[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]),
        np.array([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]]),
    ]


def sample_sphere(elevation, azimuth, radius=1.0):
    """Convert spherical (elevation, azimuth in radians) to a Cartesian point on a sphere."""
    x = radius * np.cos(elevation) * np.cos(azimuth)
    y = radius * np.sin(elevation)
    z = radius * np.cos(elevation) * np.sin(azimuth)
    return np.array([x, y, z])


def sample_sphere_mv(elevation, azimuth, radius=1.0):
    """Sample four camera positions on a sphere at 90-degree azimuthal intervals."""
    return [
        sample_sphere(elevation, azimuth + shift, radius)
        for shift in (0, np.pi / 2, np.pi, 3 * np.pi / 2)
    ]
