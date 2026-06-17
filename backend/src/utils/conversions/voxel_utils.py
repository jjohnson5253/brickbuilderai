#!/usr/bin/env python3
"""
Voxel utility functions for filling interior voxels and detecting thin regions.
"""

import numpy as np
from typing import Tuple
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt


def save_voxel_array_to_xyzrgb(voxel_array: np.ndarray, color_array: np.ndarray, output_path: str) -> None:
    """
    Save voxel and color arrays to .xyzrgb format.
    
    Args:
        voxel_array: 3D boolean array
        color_array: 3D RGB array (values 0-255 or 0-1)
        output_path: Path to save the .xyzrgb file
    """
    # Get occupied voxel coordinates
    coords = np.argwhere(voxel_array)
    
    # Get colors for occupied voxels
    colors = color_array[voxel_array]
    
    # Normalize color values to 0-255 range
    if colors.max() <= 1.0:
        colors = (colors * 255).astype(int)
    else:
        colors = colors.astype(int)
    
    # Write to file
    with open(output_path, 'w') as f:
        for (x, y, z), (r, g, b) in zip(coords, colors):
            f.write(f"{x} {y} {z} {r} {g} {b}\n")
    
    print(f"  💾 Saved debug XYZRGB: {output_path} ({len(coords)} voxels)")


def fill_interior_voxels(voxel_array: np.ndarray, color_array: np.ndarray, 
                        shell_thickness: int = 3) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Fill the interior of a voxel mesh with a configurable shell thickness.
    
    Following the Legolization paper: "We keep all voxels that are within N voxel-width 
    from the surface voxels (hence preserving the connectivity of the voxelized shape)."
    
    Args:
        voxel_array: 3D boolean array where True = voxel exists (surface voxels)
        color_array: 3D RGB array with colors for each voxel
        shell_thickness: Number of voxel layers to fill inward from surface (default: 3)
                        Set to 0 for surface only, or None/-1 for completely filled
        
    Returns:
        filled_voxel_array: Voxel array with interior filled to specified thickness
        filled_color_array: Color array with colors for filled voxels
        surface_mask: Boolean array where True = original surface voxel (not interior fill)
    """
    from collections import deque
    
    print(f"🔍 Filling interior voxels (shell thickness: {shell_thickness})...")
    original_count = voxel_array.sum()
    
    # Create a padded array to ensure we can flood fill from outside
    padded_shape = tuple(s + 2 for s in voxel_array.shape)
    padded_voxels = np.zeros(padded_shape, dtype=bool)
    padded_voxels[1:-1, 1:-1, 1:-1] = voxel_array
    
    # Track which voxels are reachable from outside (exterior air)
    exterior = np.zeros(padded_shape, dtype=bool)
    
    # Flood fill from corner (0,0,0) which is guaranteed to be outside
    queue = deque([(0, 0, 0)])
    exterior[0, 0, 0] = True
    
    # 6-connectivity (face neighbors only)
    neighbors = [(-1,0,0), (1,0,0), (0,-1,0), (0,1,0), (0,0,-1), (0,0,1)]
    
    while queue:
        x, y, z = queue.popleft()
        
        for dx, dy, dz in neighbors:
            nx, ny, nz = x + dx, y + dy, z + dz
            
            # Check bounds
            if not (0 <= nx < padded_shape[0] and 
                   0 <= ny < padded_shape[1] and 
                   0 <= nz < padded_shape[2]):
                continue
            
            # If not already visited and not a voxel, mark as exterior
            if not exterior[nx, ny, nz] and not padded_voxels[nx, ny, nz]:
                exterior[nx, ny, nz] = True
                queue.append((nx, ny, nz))
    
    # Extract the non-padded exterior mask
    exterior_unpadded = exterior[1:-1, 1:-1, 1:-1]
    
    # Interior voxels are those that are NOT exterior and NOT already filled
    all_interior = ~exterior_unpadded & ~voxel_array
    
    # If shell_thickness is None or negative, fill completely
    # If shell_thickness is 0, skip interior filling
    if shell_thickness == 0:
        interior_to_fill = np.zeros_like(voxel_array, dtype=bool)
    elif shell_thickness is None or shell_thickness < 0:
        interior_to_fill = all_interior
    else:
        # Calculate distance from each interior voxel to nearest surface voxel
        from scipy.ndimage import distance_transform_edt
        
        # Distance transform: gives distance from each empty voxel to nearest surface voxel
        distance_from_surface = distance_transform_edt(~voxel_array)
        
        # Only fill interior voxels within shell_thickness of the surface
        interior_to_fill = all_interior & (distance_from_surface <= shell_thickness)
    
    # Create filled arrays
    filled_voxel_array = voxel_array.copy()
    filled_voxel_array |= interior_to_fill
    filled_color_array = color_array.copy()
    
    # Find the most prevalent color in the color_array
    from collections import Counter
    all_colors = color_array[voxel_array]
    color_counts = Counter(map(tuple, all_colors))
    most_common_color = np.array(color_counts.most_common(1)[0][0]) if color_counts else np.array([0.949, 0.804, 0.216])
    
    # Set interior voxels to the most prevalent color
    filled_color_array[interior_to_fill] = most_common_color
    
    # Get shell coordinates for color assignment
    shell_coords = np.argwhere(voxel_array)
    
    # NOTE: Nearest neighbor color assignment disabled - interior voxels stay yellow
    # Assign colors to interior voxels using nearest neighbor from shell
    # if interior_to_fill.sum() > 0:
    #     # Get coordinates of interior voxels
    #     interior_coords = np.argwhere(interior_to_fill)
    #     
    #     if len(shell_coords) > 0:
    #         # Build KD-tree for nearest neighbor lookup
    #         tree = cKDTree(shell_coords)
    #         distances, indices = tree.query(interior_coords)
    #         
    #         # Assign each interior voxel the color of its nearest shell voxel
    #         for i, (x, y, z) in enumerate(interior_coords):
    #             nearest_shell = shell_coords[indices[i]]
    #             filled_color_array[x, y, z] = color_array[tuple(nearest_shell)]
    
    filled_count = filled_voxel_array.sum()
    added_count = filled_count - original_count
    
    print(f"  ✅ Total added: {added_count:,} voxels")
    print(f"  📊 Total voxels: {original_count:,} → {filled_count:,}")
    
    # Surface mask: True for voxels on the OUTER surface (adjacent to exterior air)
    # A voxel is on the outer surface if it has at least one exterior neighbor
    from scipy.ndimage import binary_dilation
    
    # Dilate exterior in PADDED space (before removing padding)
    # This ensures boundary voxels can detect exterior air at the bounding box edges
    dilated_exterior_padded = binary_dilation(exterior)
    
    # Now extract the unpadded region
    dilated_exterior = dilated_exterior_padded[1:-1, 1:-1, 1:-1]
    
    # Outer surface = voxels that touch the exterior (dilated exterior AND filled voxels)
    surface_mask = dilated_exterior & filled_voxel_array
    
    interior_voxel_count = filled_voxel_array.sum() - surface_mask.sum()
    print(f"  🔲 Outer surface voxels: {surface_mask.sum():,}")
    print(f"  🔳 Interior voxels: {interior_voxel_count:,}")
    
    # Color all interior voxels with the most prevalent surface color
    interior_mask = filled_voxel_array & ~surface_mask
    filled_color_array[interior_mask] = most_common_color
    # Uncomment to save xyzrgb with interior voxels colored:
    # print(f"  🟡 DEBUG: Colored {interior_mask.sum()} interior voxels yellow")
    # save_voxel_array_to_xyzrgb(filled_voxel_array, filled_color_array, "debug_interior.xyzrgb")
    
    return filled_voxel_array, filled_color_array, surface_mask


def detect_thin_regions(voxel_array: np.ndarray, 
                        color_array: np.ndarray,
                        thin_erosion_steps: int = 1,
                        thin_dilation_steps: int = 1,
                        dilate_thin_regions: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect thin regions in a voxel structure and optionally dilate them for stability.
    
    Thin region detection works by:
    1. Fill the structure completely (to get accurate erosion)
    2. Erode with 26-connectivity to shrink the structure
    3. Dilate the erosion with 26-connectivity to restore thick regions
    4. Voxels from original that fall outside this eroded+dilated mask are "thin"
    5. Only dilate those thin regions
    
    Args:
        voxel_array: 3D boolean array where True = voxel exists
        color_array: 3D RGB array with colors for each voxel
        thin_erosion_steps: Number of erosion iterations for thin region detection (default: 1)
        thin_dilation_steps: Number of dilation iterations for thin region detection (default: 1)
        dilate_thin_regions: Whether to dilate thin regions outward (default: True)
        
    Returns:
        result_voxel_array: Voxel array with thin regions dilated
        result_color_array: Color array with colors for dilated voxels
    """
    from collections import deque
    from scipy.ndimage import binary_dilation, binary_erosion
    
    print(f"🔍 Detecting thin regions (erosion: {thin_erosion_steps}, dilation: {thin_dilation_steps})...")
    
    # First, compute the fully-filled interior for accurate thin region detection
    # This matches the original behavior where erosion was done on fully-filled structure
    padded_shape = tuple(s + 2 for s in voxel_array.shape)
    padded_voxels = np.zeros(padded_shape, dtype=bool)
    padded_voxels[1:-1, 1:-1, 1:-1] = voxel_array
    
    exterior = np.zeros(padded_shape, dtype=bool)
    queue = deque([(0, 0, 0)])
    exterior[0, 0, 0] = True
    neighbors = [(-1,0,0), (1,0,0), (0,-1,0), (0,1,0), (0,0,-1), (0,0,1)]
    
    while queue:
        x, y, z = queue.popleft()
        for dx, dy, dz in neighbors:
            nx, ny, nz = x + dx, y + dy, z + dz
            if (0 <= nx < padded_shape[0] and 
                0 <= ny < padded_shape[1] and 
                0 <= nz < padded_shape[2]):
                if not exterior[nx, ny, nz] and not padded_voxels[nx, ny, nz]:
                    exterior[nx, ny, nz] = True
                    queue.append((nx, ny, nz))
    
    exterior_unpadded = exterior[1:-1, 1:-1, 1:-1]
    all_interior = ~exterior_unpadded & ~voxel_array
    
    # Create fully-filled structure for erosion (original surface + ALL interior)
    filled_structure = voxel_array | all_interior
    
    # 6-connectivity structuring element (face neighbors only)
    structure_6conn = np.array([
        [[0, 0, 0],
         [0, 1, 0],
         [0, 0, 0]],
        [[0, 1, 0],
         [1, 1, 1],
         [0, 1, 0]],
        [[0, 0, 0],
         [0, 1, 0],
         [0, 0, 0]]
    ], dtype=bool)
    
    # 26-connectivity structuring element (all neighbors including diagonals)
    structure_26conn = np.ones((3, 3, 3), dtype=bool)
    
    # Erode the FULLY-FILLED structure to shrink it (26-connectivity for more aggressive erosion)
    eroded = binary_erosion(filled_structure, structure=structure_26conn, iterations=thin_erosion_steps)
    
    # Dilate the eroded structure to restore thick regions (26-connectivity)
    thick_mask = binary_dilation(eroded, structure=structure_26conn, iterations=thin_erosion_steps)
    
    # Thin voxels are ORIGINAL surface voxels that fall outside the thick mask
    thin_voxels = voxel_array & ~thick_mask
    
    # Track new thin voxels for test coloring
    new_thin_voxels = np.zeros_like(voxel_array, dtype=bool)
    
    # Create result arrays
    result_voxel_array = voxel_array.copy()
    result_color_array = color_array.copy()
    
    # Get coordinates for color assignment
    shell_coords = np.argwhere(voxel_array)
    
    # Dilate only the thin voxels using 6-connectivity
    if dilate_thin_regions and thin_voxels.sum() > 0:
        dilated_thin = binary_dilation(thin_voxels, structure=structure_6conn, iterations=thin_dilation_steps)
        
        # Only keep new voxels (outside the original structure)
        new_thin_voxels = dilated_thin & ~result_voxel_array
        
        # Add to result array
        result_voxel_array |= new_thin_voxels
        
        print(f"  🔧 Added {new_thin_voxels.sum():,} voxels from thin region dilation")
        
        # Assign colors to new thin region voxels using nearest neighbor
        if new_thin_voxels.sum() > 0:
            new_thin_coords = np.argwhere(new_thin_voxels)
            
            if len(shell_coords) > 0:
                tree = cKDTree(shell_coords)
                distances, indices = tree.query(new_thin_coords)
                
                # Assign each new voxel the color of its nearest voxel
                for i, (x, y, z) in enumerate(new_thin_coords):
                    nearest_shell = shell_coords[indices[i]]
                    result_color_array[x, y, z] = color_array[tuple(nearest_shell)]
    
    # TEST MODE: Color thin regions red, everything else white
    # Thin voxels (original + dilated) = red
    result_color_array[thin_voxels] = [1.0, 0.0, 0.0]
    result_color_array[new_thin_voxels] = [1.0, 0.0, 0.0]
    # Non-thin voxels = white  
    non_thin_voxels = voxel_array & ~thin_voxels
    result_color_array[non_thin_voxels] = [1.0, 1.0, 1.0]
    
    print(f"  ✅ Thin region detection complete")
    print(f"  📊 Thin voxels detected: {thin_voxels.sum():,}")
    
    return result_voxel_array, result_color_array


def downsample_xyzrgb(xyzrgb_content: str, voxel_size: int) -> str:
    """
    Downsample XYZRGB data so the longest axis fits within *voxel_size* cells.

    Each line in the input is ``x y z r g b`` with integer grid coordinates
    and integer RGB values (0-255).  The function bins voxels into larger
    cells by dividing coordinates by a computed scale factor then flooring.
    Colours within each bin are averaged.

    Args:
        xyzrgb_content: The XYZRGB text (newline-separated ``x y z r g b``).
        voxel_size: Target resolution — the longest axis of the output will
                    have at most this many cells.

    Returns:
        Downsampled XYZRGB text in the same format.
    """
    data = np.loadtxt(xyzrgb_content.splitlines())
    if data.ndim == 1:
        data = data.reshape(1, -1)

    coords = data[:, :3].astype(int)
    colors = data[:, 3:6].astype(np.float64)

    # Current extent per axis
    mins = coords.min(axis=0)
    maxs = coords.max(axis=0)
    extents = maxs - mins + 1  # number of unique positions per axis

    current_max = int(extents.max())
    if current_max <= voxel_size:
        # Already at or below the target resolution — nothing to do
        return xyzrgb_content

    scale = current_max / voxel_size

    # Map each coordinate into a downsampled bin
    binned = np.floor((coords - mins) / scale).astype(int)

    # Aggregate colours per bin by averaging
    # Use a dict keyed by (bx, by, bz) -> (colour_sum, count)
    from collections import defaultdict
    buckets: dict[tuple, list] = defaultdict(lambda: [np.zeros(3, dtype=np.float64), 0])
    for i in range(len(binned)):
        key = (int(binned[i, 0]), int(binned[i, 1]), int(binned[i, 2]))
        buckets[key][0] += colors[i]
        buckets[key][1] += 1

    lines: list[str] = []
    for (x, y, z), (csum, cnt) in sorted(buckets.items()):
        r, g, b = np.round(csum / cnt).astype(int)
        lines.append(f"{x} {y} {z} {r} {g} {b}")

    print(
        f"  📉 Downsampled XYZRGB: {len(data)} voxels -> {len(lines)} voxels "
        f"(target {voxel_size}, scale {scale:.2f})"
    )
    return "\n".join(lines)
