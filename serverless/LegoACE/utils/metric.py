import trimesh
import open3d as o3d
import numpy as np
import ot

def sample_points_from_mesh(mesh_path, num_samples=2048):
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    sampled_pcd = mesh.sample_points_uniformly(number_of_points=num_samples)
    return sampled_pcd

def extract_points_from_mesh(mesh_path, num_samples=2048):
    mesh = trimesh.load_mesh(mesh_path)
    vertices = mesh.vertices
    
    # If there are more vertices than needed, randomly sample them
    if len(vertices) > num_samples:
        sampled_indices = np.random.choice(len(vertices), num_samples, replace=False)
        sampled_vertices = vertices[sampled_indices]
    else:
        sampled_vertices = vertices  # If fewer vertices than needed, return all vertices
    
    return sampled_vertices

def chamfer_distance(points1, points2):
    """
    Compute Chamfer distance between two point sets.
    points1, points2: (N, D) numpy arrays representing point sets of size N in D dimensions.
    """
    dist1 = np.linalg.norm(points1[:, np.newaxis] - points2, axis=2)  # (N, M) distance matrix
    dist2 = np.linalg.norm(points2[:, np.newaxis] - points1, axis=2)  # (M, N) distance matrix
    
    # Compute the minimum distance from each point in points1 to points2 and vice versa
    min_dist1 = np.min(dist1, axis=1)  # (N,) minimum distances from points1 to points2
    min_dist2 = np.min(dist2, axis=1)  # (M,) minimum distances from points2 to points1
    
    # Return the average of the minimum distances from both sets
    return np.mean(min_dist1) + np.mean(min_dist2)

def compute_pairwise_distances(points1, points2):
    """
    Compute the pairwise Euclidean distance matrix between two sets of points.
    """
    dist_matrix = np.linalg.norm(points1[:, np.newaxis] - points2, axis=2)
    return dist_matrix

def compute_emd(points1, points2):
    """
    Compute Earth Mover's Distance (EMD) between two point clouds.
    Assumes uniform mass for each point.
    """
    # Create uniform distributions for the points
    a = np.ones(len(points1)) / len(points1)
    b = np.ones(len(points2)) / len(points2)
    
    # Compute the pairwise distance matrix
    dist_matrix = compute_pairwise_distances(points1, points2)
    
    # Compute the Earth Mover's Distance (Wasserstein distance)
    emd_distance = ot.emd2(a, b, dist_matrix)
    
    return emd_distance

def compute_EMD(mesh_path1, mesh_path2):
    points_1 = extract_points_from_mesh(mesh_path1)
    points_2 = extract_points_from_mesh(mesh_path2)

    emd = compute_emd(points_1, points_2)

    return emd

def compute_CD(mesh_path1, mesh_path2):
    points_1 = sample_points_from_mesh(mesh_path1)
    points_2 = sample_points_from_mesh(mesh_path2)
    
    points_1 = np.asarray(points_1.points)
    points_2 = np.asarray(points_2.points)

    cd = chamfer_distance(points_1, points_2)

    return cd

def compute_cd_and_emd(mesh_path1, mesh_path2):
    points_1 = sample_points_from_mesh(mesh_path1)
    points_2 = sample_points_from_mesh(mesh_path2)
    
    points_1 = np.asarray(points_1.points)
    points_2 = np.asarray(points_2.points)

    cd = chamfer_distance(points_1, points_2)
    emd = compute_emd(points_1, points_2)

    return cd, emd