import time
from queue import PriorityQueue
from typing import Callable

import networkx as nx
import numpy as np

from ...data.brick_library import brick_library, dimensions_to_brick_id
from ...data.brick_structure import Brick, BrickStructure, ConnectivityBrickStructure
from ...stability_analysis.stability_analysis import StabilityConfig, stability_score


def first_zero_idx(arr: np.ndarray, axis: int = -1) -> np.ndarray:
    """
    Finds the index of the first occurrence of 0 along axis
    Returns the length of the last dimension if no zero occurs.
    """
    arr_eq_zero = arr == 0
    return np.where(arr_eq_zero.any(axis=axis), np.argmax(arr_eq_zero, axis=axis), arr.shape[axis])


def first_nonzero_idx(arr: np.ndarray, axis: int = -1) -> np.ndarray:
    return first_zero_idx(arr == 0, axis)


def k_ring_neighbors(node, k: int, graph: nx.Graph) -> list:
    shortest_paths = nx.single_source_shortest_path(graph, node, cutoff=k)
    return list(shortest_paths.keys())


def valid_brick(h, w) -> bool:
    try:
        dimensions_to_brick_id(h, w)
        return True
    except ValueError:
        return False


def get_merged_brick(b1: Brick, b2: Brick) -> Brick | None:
    assert b1.z == b2.z

    if b1.x == b2.x and b1.h == b2.h and (b1.y + b1.w == b2.y or b2.y + b2.w == b1.y):
        new_h, new_w = b1.h, b1.w + b2.w
        if valid_brick(new_h, new_w):
            new_x, new_y = b1.x, min(b1.y, b2.y)
            return Brick(h=new_h, w=new_w, x=new_x, y=new_y, z=b1.z)

    elif b1.y == b2.y and b1.w == b2.w and (b1.x + b1.h == b2.x or b2.x + b2.h == b1.x):
        new_h, new_w = b1.h + b2.h, b1.w
        if valid_brick(new_h, new_w):
            new_x, new_y = min(b1.x, b2.x), b1.y
            return Brick(h=new_h, w=new_w, x=new_x, y=new_y, z=b1.z)

    return None


class Voxel2Brick:
    def __init__(self, voxels: np.ndarray, max_failures: int = 10, seed: int = 42, color_array: np.ndarray = None,
                 run_stability_passes: bool = False, use_color_constraints: bool = False, 
                 hard_constraints: bool = False, wc: float = 1000.0, min_support_ratio: float = 0.5,
                 surface_mask: np.ndarray = None):
        self.voxels = voxels.astype(bool)
        self.bricks = ConnectivityBrickStructure(voxels.shape)
        self.color_array = color_array  # LDR color codes for each voxel
        self.run_stability_passes = run_stability_passes
        
        # Surface mask: True = original surface voxel, False = interior fill
        # If not provided, treat all voxels as surface (for backward compatibility)
        self.surface_mask = surface_mask if surface_mask is not None else voxels.astype(bool)
        
        # Color constraint settings (from Legolization paper)
        self.use_color_constraints = use_color_constraints and (color_array is not None)
        self.hard_constraints = hard_constraints  # True = hard constraints, False = soft constraints
        self.wc = wc  # Weight for soft constraint discarding (higher = closer to hard constraint)
        
        # Stability: minimum fraction of studs that must be supported (0.5 = at least half)
        self.min_support_ratio = min_support_ratio

        self.n_failures = 0
        self.max_failures = max_failures

        self.rng = np.random.default_rng(seed)
        
        # Track voxel positions from disconnected bricks that were removed
        self.disconnected_voxels: list[tuple[int, int, int]] = []

    @property
    def max_x(self) -> int:
        return self.voxels.shape[0]

    @property
    def max_y(self) -> int:
        return self.voxels.shape[1]

    @property
    def max_z(self) -> int:
        return self.voxels.shape[2]

    # Uncomment to use the 1x1 brick only version
    # def __call__(self) -> list[Brick]:
    #     t_start = time.time()

    #     # Use only 1x1 bricks - no greedy optimization
    #     self._brickify_voxels_1x1_only(self.voxels)
        
    #     print(f"  🧱 Placed {len(self.bricks.bricks)} 1x1 bricks (no optimization)")
    #     print(f"  ⏱️  Total time: {time.time() - t_start:.2f}s")
        
    #     return list(self.bricks.bricks.values())

    def __call__(self) -> list[Brick]:
        t_start = time.time()

        # Initialize structure greedily without color constraints
        self._brickify_voxels_greedy(self.voxels, self._greedy_priority)
        
        min_components_possible = nx.number_connected_components(self.bricks.neighbor_graph)
        
        # Optimize connectivity without color constraints
        # This builds the most structurally sound brick layout possible
        n_components = self.bricks.n_components()
        if(self.run_stability_passes):
            print("🚨 Running stability passes...")
            self.n_failures = 0
            while self.n_failures < self.max_failures:
                if n_components == min_components_possible:
                    break
                critical_voxels = self._find_critical_voxels_connectivity()
                removed_bricks = self.bricks.remove_voxel_subset(critical_voxels)
                reverse_layer_order = (self.rng.uniform() > 0.5)
                self._brickify_voxels_greedy(critical_voxels, self._component_priority,
                                            reverse_layer_order=reverse_layer_order)

                # Are the results better?
                new_n_components = self.bricks.n_components()
                if new_n_components < n_components:
                    n_components = new_n_components
                    self.n_failures = 0
                else:  # No improvement; revert merge
                    self.bricks.remove_voxel_subset(critical_voxels)
                    self.bricks.add_bricks(removed_bricks)
                    self.n_failures += 1
            
        # Detect disconnected bricks after color assignment and try to reconnect them
        disconnected_bricks = self._find_disconnected_bricks()
        if disconnected_bricks:
            print(f"  🔄 Found {len(disconnected_bricks)} disconnected bricks - attempting greedy reconnection...")
            
            # Record voxel positions from initially disconnected bricks before reconnection attempt
            for brick_id in disconnected_bricks:
                if self.bricks.node_exists(brick_id):
                    brick = self.bricks.bricks[brick_id]
                    for x in range(brick.x, brick.x + brick.h):
                        for y in range(brick.y, brick.y + brick.w):
                            self.disconnected_voxels.append((x, y, brick.z))
            
            bricks_to_remerge = self._find_bricks_around_disconnected_bricks()
            removed_bricks = self.bricks.remove_voxel_subset(bricks_to_remerge)
            
            # Temporarily use soft color constraints for reconnection to allow more flexibility
            original_hard_constraints = self.hard_constraints
            self.hard_constraints = False
            self._brickify_voxels_greedy(bricks_to_remerge, self._component_priority)
            self.hard_constraints = original_hard_constraints

        # Assign colors to all bricks based on majority color
        if self.color_array is not None:
            print(f"  🎨 Assigning colors to bricks...")
            self._assign_colors_to_bricks()

        # Check if reconnection was successful
        still_disconnected = self._find_disconnected_bricks()
        if still_disconnected:
            print(f"  ⚠️  Still have {len(still_disconnected)} disconnected bricks after greedy fill - removing them")
            self._remove_disconnected_bricks(still_disconnected)
            # Uncomment below to recolor instead of remove (for debugging):
            # self._recolor_disconnected_bricks(still_disconnected, color=39)
        else:
            print(f"  ✅ Successfully reconnected all disconnected bricks!")
        
        # Final color assignment: Split multi-color bricks into uniform-color bricks
        # Uses smart splitting that avoids creating floating bricks
        # if self.color_array is not None:
        #     print(f"  🎨 Applying colors to bricks...")
        #     initial_brick_count = len(self.bricks.bricks)
        #     kept_multicolor, split_count = self._split_bricks_by_color()
        #     final_brick_count = len(self.bricks.bricks)
        #     print(f"  ✅ Split {split_count} multi-color bricks → {final_brick_count} total bricks")
        #     if kept_multicolor > 0:
        #         print(f"  ⚠️  Kept {kept_multicolor} multi-color bricks (majority color) to prevent floating")

        # Run stability analysis
        # print(f"  🔬 Running stability analysis...")
        # brick_structure_dict = {str(i+1): {"brick_id": str(self.bricks.bricks[bid].brick_id), 
        #                                    "x": self.bricks.bricks[bid].x,
        #                                    "y": self.bricks.bricks[bid].y, 
        #                                    "z": self.bricks.bricks[bid].z,
        #                                    "ori": self.bricks.bricks[bid].ori} 
        #                        for i, bid in enumerate(self.bricks.bricks.keys())}
        
        # # Calculate the maximum extent of all bricks to determine world dimensions
        # max_x_extent = max((b.x + b.h for b in self.bricks.bricks.values()), default=self.max_x)
        # max_y_extent = max((b.y + b.w for b in self.bricks.bricks.values()), default=self.max_y)
        # max_z_extent = max((b.z + 1 for b in self.bricks.bricks.values()), default=self.max_z)
        # world_dimension = (max_x_extent, max_y_extent, max_z_extent)
        
        # stability_config = StabilityConfig(print_log=False, visualize=False, world_dimension=world_dimension)
        # analysis_score, num_vars, num_constr, total_t, solve_t = stability_score(
        #     brick_structure_dict, brick_library, stability_config
        # )
        
        # stability_max = analysis_score.max()
        # print(f"  ✅ Stability analysis complete (max score: {stability_max:.4f})")
        # print(f"     Solver variables: {num_vars}, constraints: {num_constr}")
        # print(f"     Total time: {total_t:.2f}s, optimization time: {solve_t:.2f}s")
        
        # # Collect stability scores for each brick
        # brick_stability_scores = []
        # for i, (brick_id, brick) in enumerate(self.bricks.bricks.items()):
        #     # Get the stability score for this brick's voxels (max across all voxels in the brick)
        #     brick_scores = analysis_score[brick.x:brick.x+brick.h, brick.y:brick.y+brick.w, brick.z]
        #     brick_stability = brick_scores.max()
        #     brick_stability_scores.append((brick_id, brick, brick_stability))
        
        # # Sort by stability score (descending) and show top unstable bricks
        # brick_stability_scores.sort(key=lambda x: x[2], reverse=True)
        # unstable_bricks = [b for b in brick_stability_scores if b[2] >= 0.01]
        
        # print(f"  📊 Brick stability summary:")
        # print(f"     Total bricks analyzed: {len(brick_stability_scores)}")
        # print(f"     Potentially unstable bricks (score ≥ 0.01): {len(unstable_bricks)}")
        
        # if unstable_bricks:
        #     print(f"     🚨 Top 20 most unstable bricks:")
        #     for brick_id, brick, score in unstable_bricks[:20]:
        #         print(f"        • Brick {brick_id} at ({brick.x},{brick.y},{brick.z}) size {brick.h}x{brick.w}: {score:.4f}")
            
        #     # Remove unstable bricks and their k=4 ring neighbors, then reform without color constraints
        #     print(f"  🔧 Removing {len(unstable_bricks)} unstable bricks and their 4-ring neighbors...")
        #     unstable_brick_ids = [brick_id for brick_id, _, _ in unstable_bricks]
            
        #     # Collect all bricks to remove (unstable + their 4-ring neighbors)
        #     bricks_to_remove_ids = set()
        #     for brick_id in unstable_brick_ids:
        #         if self.bricks.node_exists(brick_id):
        #             # Add the brick itself and its 4-ring neighbors
        #             k_ring_nodes = k_ring_neighbors(brick_id, 4, self.bricks.neighbor_graph)
        #             bricks_to_remove_ids.update(k_ring_nodes)
            
        #     print(f"     Total bricks to remove and reform: {len(bricks_to_remove_ids)}")
            
        #     # Create voxel mask for all bricks to remove
        #     critical_voxels = np.zeros_like(self.voxels)
        #     for brick_id in bricks_to_remove_ids:
        #         if self.bricks.node_exists(brick_id):
        #             brick = self.bricks.bricks[brick_id]
        #             critical_voxels[brick.slice] = 1
            
        #     # Remove the bricks
        #     removed_bricks = self.bricks.remove_voxel_subset(critical_voxels)
        #     print(f"     Removed {len(removed_bricks)} bricks")
            
        #     # Temporarily disable color constraints for reformation
        #     original_use_color = self.use_color_constraints
        #     self.use_color_constraints = False
            
        #     # Reform without color constraints
        #     print(f"     Reforming {np.sum(critical_voxels)} voxels without color constraints...")
        #     self._brickify_voxels_greedy(critical_voxels, self._greedy_priority)
            
        #     # Re-enable original color constraint setting
        #     self.use_color_constraints = original_use_color
            
        #     # Reassign colors to the newly created bricks
        #     if self.color_array is not None:
        #         print(f"     Re-assigning colors to reformed bricks...")
        #         self._assign_colors_to_bricks()
            
        #     print(f"  ✅ Reformed unstable regions - new brick count: {len(self.bricks.bricks)}")
            
        #     # Run stability analysis again to check if reformation helped
        #     print(f"  🔬 Running second stability analysis after reformation...")
        #     brick_structure_dict = {str(i+1): {"brick_id": str(self.bricks.bricks[bid].brick_id), 
        #                                        "x": self.bricks.bricks[bid].x,
        #                                        "y": self.bricks.bricks[bid].y, 
        #                                        "z": self.bricks.bricks[bid].z,
        #                                        "ori": self.bricks.bricks[bid].ori} 
        #                            for i, bid in enumerate(self.bricks.bricks.keys())}
            
        #     max_x_extent = max((b.x + b.h for b in self.bricks.bricks.values()), default=self.max_x)
        #     max_y_extent = max((b.y + b.w for b in self.bricks.bricks.values()), default=self.max_y)
        #     max_z_extent = max((b.z + 1 for b in self.bricks.bricks.values()), default=self.max_z)
        #     world_dimension = (max_x_extent, max_y_extent, max_z_extent)
            
        #     stability_config = StabilityConfig(print_log=False, visualize=False, world_dimension=world_dimension)
        #     analysis_score_2, num_vars_2, num_constr_2, total_t_2, solve_t_2 = stability_score(
        #         brick_structure_dict, brick_library, stability_config
        #     )
            
        #     stability_max_2 = analysis_score_2.max()
        #     print(f"  ✅ Second stability analysis complete (max score: {stability_max_2:.4f})")
        #     print(f"     Solver variables: {num_vars_2}, constraints: {num_constr_2}")
        #     print(f"     Total time: {total_t_2:.2f}s, optimization time: {solve_t_2:.2f}s")
            
        #     # Check for remaining unstable bricks
        #     brick_stability_scores_2 = []
        #     for i, (brick_id, brick) in enumerate(self.bricks.bricks.items()):
        #         brick_scores = analysis_score_2[brick.x:brick.x+brick.h, brick.y:brick.y+brick.w, brick.z]
        #         brick_stability = brick_scores.max()
        #         brick_stability_scores_2.append((brick_id, brick, brick_stability))
            
        #     brick_stability_scores_2.sort(key=lambda x: x[2], reverse=True)
        #     remaining_unstable = [b for b in brick_stability_scores_2 if b[2] >= 0.01]
            
        #     if remaining_unstable:
        #         print(f"  ⚠️  Still have {len(remaining_unstable)} unstable bricks after reformation")
        #         # print(f"     🎨 Recoloring them with transparent color (15 = white)")
        #         # unstable_brick_ids_2 = [brick_id for brick_id, _, _ in remaining_unstable]
        #         # self._recolor_disconnected_bricks(unstable_brick_ids_2, color=15)
        #         print(f"     Top 10 remaining unstable bricks:")
        #         for brick_id, brick, score in remaining_unstable[:10]:
        #             print(f"        • Brick {brick_id} at ({brick.x},{brick.y},{brick.z}) size {brick.h}x{brick.w}: {score:.4f}")
        #     else:
        #         print(f"  ✅ All bricks are now stable after reformation!")
            
        #     # Update final stability score
        #     stability_max = stability_max_2
        # else:
        #     print(f"     ✅ All bricks are perfectly stable (scores < 0.01)")
        
        stability_max = 0.0  # Dummy value since stability analysis is disabled
        
        image2brick_time = time.time() - t_start
        print(f'Finished in time: {image2brick_time:.4f} s | '
              f'# bricks: {len(self.bricks.bricks)} | '
              f'# connected components: {n_components} | '
              f'# min connected components possible: {min_components_possible} | '
              f'Stability analysis: DISABLED')

        return list(self.bricks.bricks.values())

    def _brickify_voxels_greedy(
            self,
            voxel_subset: np.ndarray,
            priority: Callable,
            reverse_layer_order: bool = False,
    ) -> None:
        self._brickify_voxels(voxel_subset, lambda v, z: self._brickify_layer_greedy(v, z, priority),
                              reverse_layer_order=reverse_layer_order)

    def _brickify_voxels_merge(self, voxel_subset: np.ndarray, reverse_layer_order: bool = False) -> None:
        self._brickify_voxels(voxel_subset, self._brickify_layer_merge, reverse_layer_order=reverse_layer_order)

    def _brickify_voxels(
            self,
            voxel_subset: np.ndarray,
            layer_brickify_fn: Callable,
            reverse_layer_order: bool = False,
    ) -> None:
        min_z = first_nonzero_idx(voxel_subset.sum(axis=(0, 1)))
        max_z = self.max_z - first_nonzero_idx(voxel_subset.sum(axis=(0, 1))[::-1])
        if reverse_layer_order:
            for z in reversed(range(min_z, max_z)):
                layer_brickify_fn(voxel_subset, z)
        else:
            for z in range(min_z, max_z):
                layer_brickify_fn(voxel_subset, z)
        assert ((self.bricks.voxel_bricks != 0) == (self.voxels != 0)).all()

    def _brickify_voxels_1x1_only(self, voxel_subset: np.ndarray) -> None:
        """
        Place only 1x1 bricks - no optimization, perfect color matching.
        Each occupied voxel gets exactly one 1x1 brick.
        """
        occupied_positions = np.where(voxel_subset)
        
        for x, y, z in zip(*occupied_positions):
            brick = Brick(h=1, w=1, x=x, y=y, z=z)
            try:
                self.bricks.add_brick(brick)
            except ValueError:
                # This shouldn't happen with 1x1 bricks, but just in case
                pass

    def _brickify_layer_greedy(self, voxel_subset: np.ndarray, z: int, priority: Callable) -> None:
        brick_dimensions = ([(v['height'], v['width']) for v in brick_library.values()] +
                            [(v['width'], v['height']) for v in brick_library.values()
                             if v['height'] != v['width']])

        # Enumerate possible brick placements
        min_x = first_nonzero_idx(voxel_subset[..., z].sum(axis=1))
        max_x = self.max_x - first_nonzero_idx(voxel_subset[..., z].sum(axis=1)[::-1])
        min_y = first_nonzero_idx(voxel_subset[..., z].sum(axis=0))
        max_y = self.max_y - first_nonzero_idx(voxel_subset[..., z].sum(axis=0)[::-1])
        all_brick_placements = [Brick(h=h, w=w, x=x, y=y, z=z)
                                for h, w in brick_dimensions
                                for x in range(min_x, max_x - h + 1) for y in range(min_y, max_y - w + 1)]

        # Filter out bricks that are not completely contained within the voxels
        valid_brick_placements = list(filter(lambda b: voxel_subset[b.slice].all(), all_brick_placements))
        
        # Filter out bricks that don't have sufficient support (at least min_support_ratio of studs)
        # This prevents unstable placements like a 2x4 brick hanging by just 1 stud
        valid_brick_placements = list(filter(self._has_sufficient_support, valid_brick_placements))
        
        # Further filter by color constraints if enabled
        if self.use_color_constraints:
            color_valid_placements = []
            for brick in valid_brick_placements:
                if self._is_brick_color_uniform(brick):
                    color_valid_placements.append(brick)
                elif not self.hard_constraints:
                    # Soft constraints allow non-uniform bricks
                    color_valid_placements.append(brick)
            valid_brick_placements = color_valid_placements
        
        # Place bricks in order of priority
        for brick in sorted(valid_brick_placements, key=priority):
            try:
                self.bricks.add_brick(brick)
            except ValueError:
                pass
    
    def _get_shell_voxels(self, brick: Brick) -> list[tuple[int, int, int]]:
        """
        Get list of shell (surface) voxel positions for a brick.
        
        Uses surface_mask if available (which tracks original surface voxels vs interior fill).
        Otherwise falls back to checking if voxel is exposed to outside.
        """
        shell_voxels = []
        z_val = brick.z
        
        for x in range(brick.x, brick.x + brick.h):
            for y in range(brick.y, brick.y + brick.w):
                # Use surface_mask to determine if this is a surface voxel
                # surface_mask[x,y,z] is True for original surface voxels
                if self.surface_mask[x, y, z_val]:
                    shell_voxels.append((x, y, z_val))
        
        return shell_voxels
    
    def _is_brick_color_uniform(self, brick: Brick) -> bool:
        """Check if all shell (surface) voxels in brick have the same color."""
        if self.color_array is None:
            return True
        
        shell_voxels = self._get_shell_voxels(brick)
        if len(shell_voxels) == 0:
            # No surface voxels in this brick - it's entirely interior, so skip color check
            return True
        else:
            colors = np.array([self.color_array[x, y, z] for x, y, z in shell_voxels])
        
        if colors.size == 0:
            return True
        first_color = colors.flat[0]
        return (colors == first_color).all()
    
    def _assign_brick_color(self, brick: Brick) -> Brick:
        """Assign color to a brick based on its voxel colors."""
        if self.color_array is None:
            return brick
        
        colors = self.color_array[brick.slice]
        if colors.size == 0:
            return brick
        
        # Use majority color
        unique_colors, counts = np.unique(colors, return_counts=True)
        majority_color = int(unique_colors[np.argmax(counts)])
        
        return Brick(h=brick.h, w=brick.w, x=brick.x, y=brick.y, z=brick.z, color=majority_color)

    def _greedy_priority(self, brick: Brick):
        dangles = 1 if 0 < self._calc_support_ratio(brick) < 1 else 0
        shorter_side = min(brick.h, brick.w)
        ori_priority = (-1 if brick.ori == 0 else 1) * (-1) ** brick.z
        return (-dangles, -self._count_gaps(brick), -shorter_side, -brick.area, ori_priority,
                brick.x, brick.y, brick.z)

    def _component_priority(self, brick: Brick):
        return -self._count_connecting_components(brick), -brick.area, self.rng.uniform()

    def _calc_support_ratio(self, brick: Brick) -> float:
        """Calculate support ratio from below."""
        if brick.z == 0:
            return 1.0
        total_area = brick.h * brick.w
        supported_area = self.voxels[*brick.slice_2d, brick.z - 1].sum()
        return supported_area / total_area
    
    def _calc_support_ratio_above(self, brick: Brick) -> float:
        """Calculate support ratio from above."""
        if brick.z >= self.max_z - 1:
            return 1.0
        total_area = brick.h * brick.w
        supported_area = self.voxels[*brick.slice_2d, brick.z + 1].sum()
        return supported_area / total_area
    
    def _has_sufficient_support(self, brick: Brick) -> bool:
        """
        Check if a brick has sufficient support from below OR above.
        A brick needs at least min_support_ratio of its studs supported to be stable.
        For example, with min_support_ratio=0.5, a 2x4 brick needs at least 4 studs supported.
        
        1x1 bricks are always allowed since they're the smallest unit and must be placed
        to cover all voxels (even floating ones).
        """
        # 1x1 bricks are always allowed - they're the fallback for any voxel
        if brick.h == 1 and brick.w == 1:
            return True
        # Check support from below OR above
        support_below = self._calc_support_ratio(brick)
        support_above = self._calc_support_ratio_above(brick)
        return support_below >= self.min_support_ratio or support_above >= self.min_support_ratio

    def _count_gaps(self, brick: Brick) -> int:
        """
        A "gap" is a pair of voxels beneath the brick that belong to two different bricks
        (and hence those two bricks will be connected by placing the brick).
        This function returns the sum of the depths of gaps beneath the brick.
        """
        if brick.z == 0:
            return 0

        structure_under_brick = self.bricks.voxel_bricks[*brick.slice_2d, :brick.z]
        # Equals 1 at [x,y,z] if voxels [x,y,z] and [x+1,y,z] are in different bricks
        horz_gaps = structure_under_brick[:-1, :, :] != structure_under_brick[1:, :, :]
        # Equals 1 at [x,y,z] if voxels [x,y,z] and [x,y+1,z] are in different bricks
        vert_gaps = structure_under_brick[:, :-1, :] != structure_under_brick[:, 1:, :]

        # [x,y,z] = d, where d is the largest integer such that [x,y,z-i] != [x+1,y,z-i] for all i < d
        horz_gap_depths = first_zero_idx(horz_gaps[..., ::-1])
        vert_gap_depths = first_zero_idx(vert_gaps[..., ::-1])

        return horz_gap_depths.sum() + vert_gap_depths.sum()

    def _count_connecting_components(self, brick: Brick) -> int:
        """
        Returns the number of components that will be connected if brick is added to the structure.
        """
        components = set()
        if brick.z > 0:
            components |= set(np.unique(self.bricks.component_labels()[*brick.slice_2d, brick.z - 1])) - {0}
        if brick.z < self.max_z - 1:
            components |= set(np.unique(self.bricks.component_labels()[*brick.slice_2d, brick.z + 1])) - {0}
        return len(components)

    def _brickify_layer_merge(self, voxel_subset: np.ndarray, z: int) -> None:
        # Fill with 1x1 bricks
        voxel_idxs = list(zip(*np.nonzero(voxel_subset[..., z])))
        brick_1x1s = [Brick(h=1, w=1, x=x, y=y, z=z) for x, y in voxel_idxs]
        node_ids = [self.bricks.add_brick(brick) for brick in brick_1x1s]

        # Add all mergeable brick pairs to queue
        pq = PriorityQueue()
        for b1 in node_ids:
            self._add_mergeable_pairs_to_queue(b1, pq, voxel_subset)

        # Merge pairs until queue is empty
        while not pq.empty():
            _, b1, b2, merged_brick = pq.get()
            if not self.bricks.node_exists(b1) or not self.bricks.node_exists(b2):
                continue
            self.bricks.remove_brick(b1)
            self.bricks.remove_brick(b2)
            b3 = self.bricks.add_brick(merged_brick)
            self._add_mergeable_pairs_to_queue(b3, pq, voxel_subset)

    def _add_mergeable_pairs_to_queue(self, b1: int, pq: PriorityQueue, voxel_subset: np.ndarray) -> None:
        for b2 in self.bricks.neighbor_graph.neighbors(b1):
            brick1, brick2 = self.bricks.bricks[b1], self.bricks.bricks[b2]
            if brick2.z != brick1.z or not voxel_subset[brick2.slice].all():
                continue
            merged_brick = get_merged_brick(brick1, brick2)
            if merged_brick:
                # Check color constraints before adding to queue
                if self.use_color_constraints:
                    can_merge, merged_color = self._check_color_merge(brick1, brick2)
                    if not can_merge:
                        continue
                    # Update merged brick with assigned color
                    merged_brick = Brick(h=merged_brick.h, w=merged_brick.w, 
                                        x=merged_brick.x, y=merged_brick.y, z=merged_brick.z,
                                        color=merged_color)
                pq.put((self.rng.uniform(0, 1), b1, b2, merged_brick))
    
    def _check_color_merge(self, brick1: Brick, brick2: Brick) -> tuple[bool, int]:
        """
        Check if two bricks can be merged according to color constraints (Legolization paper).
        Returns (can_merge, merged_color).
        Only considers shell (surface) voxels since interior voxels don't affect visual appearance.
        
        Color assignment rules from the paper:
        Case 1: Both IGNORE → merged is IGNORE
        Case 2: One specific color, one IGNORE → merged is specific color
        Case 3: Same color → merged is that color
        Case 4: Different colors → apply hard/soft constraint logic
        """
        # Get colors from shell voxels only (not interior)
        shell_voxels1 = self._get_shell_voxels(brick1)
        shell_voxels2 = self._get_shell_voxels(brick2)
        
        if len(shell_voxels1) == 0:
            colors1 = self.color_array[brick1.slice]
        else:
            colors1 = np.array([self.color_array[x, y, z] for x, y, z in shell_voxels1])
        
        if len(shell_voxels2) == 0:
            colors2 = self.color_array[brick2.slice]
        else:
            colors2 = np.array([self.color_array[x, y, z] for x, y, z in shell_voxels2])
        
        # Get unique colors from each brick
        unique1 = np.unique(colors1)
        unique2 = np.unique(colors2)
        
        # For simplicity, use the first color if brick has uniform color, otherwise get majority
        if len(unique1) == 1:
            c1 = int(unique1[0])
        else:
            # Multi-color brick - use majority color
            vals, counts = np.unique(colors1, return_counts=True)
            c1 = int(vals[np.argmax(counts)])
            
        if len(unique2) == 1:
            c2 = int(unique2[0])
        else:
            # Multi-color brick - use majority color
            vals, counts = np.unique(colors2, return_counts=True)
            c2 = int(vals[np.argmax(counts)])
        
        # Case 3: Same color
        if c1 == c2:
            return True, c1
        
        # Case 4: Different colors
        if self.hard_constraints:
            # Hard constraint: cannot merge bricks with different colors
            return False, -1
        else:
            # Soft constraint: use importance sampling strategy
            # Count color-inconsistent voxels for each choice
            merged_colors = np.concatenate([colors1.flatten(), colors2.flatten()])
            e1 = np.sum(merged_colors != c1)  # Inconsistencies if we choose c1
            e2 = np.sum(merged_colors != c2)  # Inconsistencies if we choose c2
            
            # Avoid division by zero
            e1 = max(e1, 1)
            e2 = max(e2, 1)
            
            # Probability to discard the merge
            p_discard = self.wc / (1.0/e1 + 1.0/e2 + self.wc)
            
            if self.rng.uniform() < p_discard:
                return False, -1  # Discard merge
            
            # Probability to choose c1 or c2
            p1 = (1.0/e1) / (1.0/e1 + 1.0/e2 + self.wc)
            
            if self.rng.uniform() < p1 / (1 - p_discard):
                return True, c1
            else:
                return True, c2

    def _assign_colors_to_bricks(self) -> None:
        """
        Assign colors to all bricks based on the majority color of shell (surface) voxels.
        Shell voxels are those visible from outside - they determine the brick's visual appearance.
        """
        if self.color_array is None:
            return
        
        brick_ids = list(self.bricks.bricks.keys())
        for brick_id in brick_ids:
            if not self.bricks.node_exists(brick_id):
                continue
            
            brick = self.bricks.bricks[brick_id]
            
            # Get shell voxels using helper method
            shell_voxels = self._get_shell_voxels(brick)
            
            # Get colors of shell voxels only
            if len(shell_voxels) == 0:
                # Fallback: if no shell voxels found (shouldn't happen), use all voxels
                colors_in_brick = self.color_array[brick.slice]
            else:
                shell_colors = [self.color_array[x, y, z] for x, y, z in shell_voxels]
                colors_in_brick = np.array(shell_colors)
            
            if colors_in_brick.size == 0:
                continue
            
            # Find majority color among shell voxels
            unique_colors, counts = np.unique(colors_in_brick, return_counts=True)
            majority_color = int(unique_colors[np.argmax(counts)])
            
            # Replace brick with colored version
            self.bricks.remove_brick(brick_id)
            colored_brick = Brick(h=brick.h, w=brick.w, x=brick.x, y=brick.y, z=brick.z,
                                    color=majority_color)
            self.bricks.add_brick(colored_brick)

    def _find_disconnected_bricks(self) -> list[int]:
        """
        Find bricks that are not connected to the main structure via connection_graph.
        Returns a list of brick IDs that are disconnected (not in the largest component).
        """
        if len(self.bricks.bricks) == 0:
            return []
        
        # Get all connected components from the connection_graph
        components = list(nx.connected_components(self.bricks.connection_graph))
        
        if len(components) <= 1:
            return []  # Everything is connected
        
        # Find the largest component (main structure)
        largest_component = max(components, key=len)
        
        # All bricks not in the largest component are disconnected
        disconnected = []
        for component in components:
            if component != largest_component:
                disconnected.extend(component)
        
        return disconnected
    
    def _find_bricks_around_disconnected_bricks(self, k_ring: int = 1) -> np.ndarray:
        """
        Find the voxels of bricks surrounding disconnected bricks.
        Similar to _get_critical_voxels but for all disconnected bricks.
        Returns a voxel array marking the bricks to be removed and re-added.
        
        Args:
            k_ring: Size of k-ring neighborhood (default=1 only immediate neighbording bricks)
        """
        disconnected_brick_ids = self._find_disconnected_bricks()
        if not disconnected_brick_ids:
            return np.zeros_like(self.voxels)
        
        critical_voxels = np.zeros_like(self.voxels)
        
        # For each disconnected brick, find its k-ring neighbors
        for brick_id in disconnected_brick_ids:
            if not self.bricks.node_exists(brick_id):
                continue
            
            # Get k-ring neighbors around this disconnected brick
            # Use fixed k_ring size rather than _k_ring_size() which depends on n_failures
            critical_nodes = k_ring_neighbors(brick_id, k_ring, self.bricks.neighbor_graph)
            
            # Mark all voxels in these bricks for removal and re-addition
            for node in critical_nodes:
                if self.bricks.node_exists(node):
                    brick = self.bricks.bricks[node]
                    critical_voxels[brick.slice] = 1
        
        return critical_voxels

    def _remove_disconnected_bricks(self, disconnected_brick_ids: list[int]) -> None:
        """
        Remove all disconnected bricks from the structure.
        Records the voxel positions in self.disconnected_voxels before removal.
        
        Args:
            disconnected_brick_ids: List of brick IDs to remove
        """
        for brick_id in disconnected_brick_ids:
            if not self.bricks.node_exists(brick_id):
                continue
            # Record all voxel positions from this brick before removal
            brick = self.bricks.bricks[brick_id]
            for x in range(brick.x, brick.x + brick.h):
                for y in range(brick.y, brick.y + brick.w):
                    self.disconnected_voxels.append((x, y, brick.z))
            self.bricks.remove_brick(brick_id)

    def _recolor_disconnected_bricks(self, disconnected_brick_ids: list[int], color: int) -> None:
        """
        Recolor all disconnected bricks to a specific color (for debugging).
        
        Args:
            disconnected_brick_ids: List of brick IDs to recolor
            color: LDR color code to apply (e.g., 39 for light bluish violet)
        """
        for brick_id in disconnected_brick_ids:
            if not self.bricks.node_exists(brick_id):
                continue
            
            brick = self.bricks.bricks[brick_id]
            
            # Replace brick with recolored version
            self.bricks.remove_brick(brick_id)
            recolored_brick = Brick(h=brick.h, w=brick.w, x=brick.x, y=brick.y, z=brick.z,
                                    color=color)
            self.bricks.add_brick(recolored_brick)

    def _find_critical_voxels_connectivity(self) -> np.ndarray:
        """
        From the Legolization paper
        """
        nodes = list(self.bricks.bricks.keys())
        pvals = np.array([self._num_neighboring_components(node) - 1
                          for node in nodes], dtype=float)
        pvals /= pvals.sum()

        selected_node_idx = np.argmax(self.rng.multinomial(1, pvals))
        weakest_node = nodes[selected_node_idx]
        return self._get_critical_voxels(weakest_node)

    def _num_neighboring_components(self, node: int) -> int:
        components = (
                    {self.bricks.node2component()[neighbor] for neighbor in self.bricks.neighbor_graph.neighbors(node)}
                    | {self.bricks.node2component()[node]})
        return len(components)

    def _find_critical_voxels_stability(self, stability: np.ndarray) -> np.ndarray:
        """
        From the Legolization paper. Returns bricks surrounding the weakest brick in the structure
        """
        # Find weakest node in structure
        if stability.max() < 1.0:
            return np.zeros_like(self.voxels)
        weakest_node_idx = np.unravel_index(np.argmax(stability), stability.shape)
        weakest_node = self.bricks.voxel_bricks[weakest_node_idx]
        return self._get_critical_voxels(weakest_node)

    def _get_critical_voxels(self, critical_node) -> np.ndarray:
        critical_nodes = k_ring_neighbors(critical_node, self._k_ring_size(), self.bricks.neighbor_graph)
        critical_bricks = [self.bricks.bricks[n] for n in critical_nodes]
        critical_voxels = np.zeros_like(self.voxels)
        for brick in critical_bricks:
            critical_voxels[brick.slice] = 1
        return critical_voxels

    def _k_ring_size(self) -> int:
        return self.n_failures // 10 + 1


def voxel2brick(voxels: np.ndarray, color_array: np.ndarray = None, run_stability_passes: bool = False,
                use_color_constraints: bool = True, hard_constraints: bool = True, 
                wc: float = 1000.0, min_support_ratio: float = 0.5, 
                surface_mask: np.ndarray = None, **kwargs) -> BrickStructure:
    """
    Convert voxel array to optimized brick structure.
    
    Args:
        voxels: 3D boolean array of occupied voxels
        color_array: LDR color codes for each voxel
        use_color_constraints: Whether to apply color constraints during optimization
        hard_constraints: True = hard constraints (exact color match), False = soft constraints
        wc: Weight parameter for soft constraints (higher = stricter, closer to hard)
        min_support_ratio: Minimum fraction of studs that must be supported (0.5 = at least half).
                          Prevents unstable brick placements like a 2x4 hanging by 1 stud.
        surface_mask: Boolean array where True = original surface voxel (not interior fill).
                     Used for color constraints to only consider surface voxels.
        **kwargs: Additional parameters (max_failures, seed, etc.)
    
    Returns:
        Optimized BrickStructure
    """
    v2l = Voxel2Brick(voxels, color_array=color_array, 
                      run_stability_passes=run_stability_passes,
                      use_color_constraints=use_color_constraints,
                      hard_constraints=hard_constraints, 
                      wc=wc, min_support_ratio=min_support_ratio, 
                      surface_mask=surface_mask, **kwargs)
    bricks = v2l()

    # Use the maximum dimension from the voxel array as world_dim
    world_dim = max(voxels.shape)
    brick_structure = BrickStructure(bricks, world_dim=world_dim)
    
    # Transfer disconnected voxels from solver to brick structure
    brick_structure.problematic_voxels.extend(v2l.disconnected_voxels)
    
    return brick_structure
