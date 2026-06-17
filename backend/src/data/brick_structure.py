import re
import warnings
from dataclasses import dataclass

import networkx as nx
import numpy as np

from .brick_library import (brick_library, dimensions_to_brick_id, brick_id_to_dimensions,
                                           brick_id_to_part_id, part_id_to_brick_id)
from ..stability_analysis.stability_analysis import StabilityConfig, stability_score


@dataclass(frozen=True, order=True, kw_only=True)
class Brick:
    """
    Represents a 1-unit-tall rectangular brick.
    """
    h: int
    w: int
    x: int
    y: int
    z: int
    color: int = 4  # Default to red (LDR color code 4)

    @property
    def brick_id(self) -> int:
        return dimensions_to_brick_id(self.h, self.w)

    @property
    def part_id(self) -> str:
        return brick_id_to_part_id(self.brick_id)

    @property
    def ori(self) -> int:
        return 1 if self.h > self.w else 0

    @property
    def area(self) -> int:
        return self.h * self.w

    @property
    def slice_2d(self) -> (slice, slice):
        return slice(self.x, self.x + self.h), slice(self.y, self.y + self.w)

    @property
    def slice(self) -> (slice, slice, int):
        return *self.slice_2d, self.z

    def __repr__(self):
        return self.to_txt()[:-1]

    def to_json(self) -> dict:
        return {
            'brick_id': self.brick_id,
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'ori': self.ori,
        }

    def to_txt(self) -> str:
        return f'{self.h}x{self.w} ({self.x},{self.y},{self.z})\n'

    def to_ldr(self, base_height: float = 0, color: int = 4) -> str:
        x = (self.x + self.h * 0.5) * 20
        z = (self.y + self.w * 0.5) * 20
        y = (self.z + base_height) * -24
        matrix = '0 0 1 0 1 0 -1 0 0' if self.ori == 0 else '-1 0 0 0 1 0 0 0 -1'
        line = f'1 {color} {x} {y} {z} {matrix} {self.part_id}\n'
        step_line = '0 STEP\n'
        return line + step_line

    @classmethod
    def from_json(cls, brick_json: dict):
        h, w = brick_id_to_dimensions(brick_json['brick_id'])
        if brick_json['ori'] == 1:
            h, w = w, h
        x, y, z = brick_json['x'], brick_json['y'], brick_json['z']
        return cls(h=h, w=w, x=x, y=y, z=z)

    @classmethod
    def from_txt(cls, brick_txt: str):
        brick_txt = brick_txt.strip()
        match = re.fullmatch(r'(\d+)x(\d+) \((\d+),(\d+),(\d+)\)', brick_txt)
        if match is None:
            raise ValueError(f'Text Format brick is ill-formatted: {brick_txt}')

        h, w, x, y, z = map(int, match.group(1, 2, 3, 4, 5))
        return cls(h=h, w=w, x=x, y=y, z=z)

    @classmethod
    def from_ldr(cls, brick_ldr: str):
        ldr_components = brick_ldr.strip().split()
        match ldr_components:
            case ['1', _, x0, y0, z0, *matrix, part_id]:
                x0, y0, z0 = map(float, (x0, y0, z0))
                matrix_str = ' '.join(matrix)
                if matrix_str == '0 0 1 0 1 0 -1 0 0':
                    ori = 0
                elif matrix_str == '-1 0 0 0 1 0 0 0 -1':
                    ori = 1
                else:
                    raise ValueError(f'Invalid transformation matrix: {matrix_str}')

                h, w = brick_id_to_dimensions(part_id_to_brick_id(part_id))
                if ori == 1:
                    h, w = w, h

                x = int(x0 / 20 - h * 0.5)
                y = int(z0 / 20 - w * 0.5)
                z = int(-y0 / 24)

                return cls(h=h, w=w, x=x, y=y, z=z)
            case _:
                raise ValueError(f"LDR format is ill-formatted: {brick_ldr}")


class BrickStructure:
    """
    Represents a brick structure in the form of a list of bricks.
    """

    def __init__(self, bricks: list[Brick], world_dim: int = 20):
        self.world_dim = world_dim

        # Check if structure starts at ground level
        z0 = min((brick.z for brick in bricks), default=0)
        if z0 != 0:
            warnings.warn('Brick structure does not start at ground level z=0.')

        # Build structure from bricks
        self.bricks = []
        self.voxel_occupancy = np.zeros((world_dim, world_dim, world_dim), dtype=int)
        # Track problematic voxels (disconnected or floating) as list of (x, y, z) tuples
        self.problematic_voxels: list[tuple[int, int, int]] = []
        for brick in bricks:
            self.add_brick(brick)

    def __len__(self):
        return len(self.bricks)

    def __repr__(self):
        return self.to_txt()

    def __eq__(self, other) -> bool:
        if not isinstance(other, BrickStructure):
            return NotImplemented
        return self.bricks == other.bricks

    def to_json(self) -> dict:
        return {str(i + 1): brick.to_json() for i, brick in enumerate(self.bricks)}

    def to_txt(self) -> str:
        return ''.join([brick.to_txt() for brick in self.bricks])

    def save_numpy_voxels(self, filepath: str) -> None:
        """
        Save the voxel occupancy numpy array to a file before LDR conversion.
        
        Args:
            filepath: Path where to save the numpy array (should end with .npy)
        """
        import numpy as np
        np.save(filepath, self.voxel_occupancy)
    
    def _reorder_bricks_for_stability(self, bricks: list[Brick]) -> tuple[list[Brick], set[Brick]]:
        """
        Reorder bricks to place each at its absolute earliest possible position.

        Places ALL below-supported bricks per round (safe because z-first sorting
        guarantees monotonic placement), but only ONE above-supported brick per
        round (to allow correct interleaving with newly-unlocked below bricks).
        Uses an index-set for O(1) removal instead of O(n) list removal.

        Complexity: O(n × rounds) where rounds ≈ max(z), down from O(n²).

        Args:
            bricks: List of bricks to reorder

        Returns:
            Tuple of (ordered bricks list, set of deferred/force-placed bricks)
        """
        if not bricks:
            return bricks, set()

        temp_structure = BrickStructure([], world_dim=self.world_dim)
        ordered_bricks = []
        remaining_set = set(range(len(bricks)))  # indices into bricks list
        deferred_bricks = set()

        # Track which voxels belong to deferred bricks
        deferred_voxels = np.zeros((self.world_dim, self.world_dim, self.world_dim), dtype=bool)

        while remaining_set:
            # Categorize all remaining bricks
            supported_below = []
            supported_above = []

            for idx in remaining_set:
                brick = bricks[idx]
                support = temp_structure._get_brick_support_type(brick)
                if support == 'ground' or support == 'below':
                    supported_below.append(idx)
                elif support == 'above':
                    supported_above.append(idx)

            # Sort supported_below by lowest z first (ground-up building)
            supported_below.sort(key=lambda i: (bricks[i].z, bricks[i].x, bricks[i].y))
            # Sort supported_above by highest z first (top-down building)
            supported_above.sort(key=lambda i: (-bricks[i].z, bricks[i].x, bricks[i].y))

            placed_this_round = False

            # First priority: place ALL bricks supported from below this round.
            # This is safe because z-first sorting means a brick at z=k can only
            # unlock bricks at z=k+1, which sort after all z<=k bricks.
            if supported_below:
                for idx in supported_below:
                    brick = bricks[idx]
                    temp_structure.add_brick(brick)
                    ordered_bricks.append(brick)
                    remaining_set.discard(idx)
                    placed_this_round = True

                    # Check if this brick is supported ONLY by deferred voxels
                    if brick.z > 0:
                        support_voxels = temp_structure.voxel_occupancy[brick.slice_2d[0], brick.slice_2d[1], brick.z - 1]
                        deferred_support = deferred_voxels[brick.slice_2d[0], brick.slice_2d[1], brick.z - 1]
                        if np.all((support_voxels > 0) == deferred_support):
                            deferred_bricks.add(brick)
                            deferred_voxels[brick.slice] = True

            # Second priority: place ONE brick supported from above (highest z first).
            # Only one per round so we re-categorize — placing this brick may
            # unlock below-supported bricks that should take priority next round.
            elif supported_above:
                idx = supported_above[0]
                brick = bricks[idx]
                temp_structure.add_brick(brick)
                ordered_bricks.append(brick)
                remaining_set.discard(idx)
                placed_this_round = True
                deferred_bricks.add(brick)  # Track hanging bricks as deferred
                deferred_voxels[brick.slice] = True

            # Safety: force-place one brick to avoid infinite loop
            if not placed_this_round:
                forced_idx = max(remaining_set, key=lambda i: (-bricks[i].z, bricks[i].x, bricks[i].y))
                forced_brick = bricks[forced_idx]
                temp_structure.add_brick(forced_brick)
                ordered_bricks.append(forced_brick)
                remaining_set.discard(forced_idx)
                deferred_bricks.add(forced_brick)  # Track this as deferred
                deferred_voxels[forced_brick.slice] = True

        return ordered_bricks, deferred_bricks

    def _get_brick_support_type(self, brick: Brick) -> str:
        """
        Determine how a brick is supported in the current structure.
        
        Returns:
            'ground' - brick is on ground level (z=0)
            'below' - brick has support from below
            'above' - brick only has support from above
            'floating' - brick has no support
        """
        if brick.z == 0:
            return 'ground'
        
        has_support_below = np.any(
            self.voxel_occupancy[brick.slice_2d[0], brick.slice_2d[1], brick.z - 1]
        )
        if has_support_below:
            return 'below'
        
        has_support_above = (
            brick.z != self.world_dim - 1 and 
            np.any(self.voxel_occupancy[brick.slice_2d[0], brick.slice_2d[1], brick.z + 1])
        )
        if has_support_above:
            return 'above'
        
        return 'floating'

    def _compute_exterior_mask(self) -> np.ndarray:
        """
        Compute a boolean mask of exterior (air reachable from outside) voxels
        via flood-fill from (0,0,0) on a 1-padded occupancy grid.

        Returns:
            np.ndarray of shape (world_dim, world_dim, world_dim), True = exterior air.
        """
        from scipy.ndimage import label

        # Padded grid so the outside border is guaranteed to be air
        padded_shape = tuple(s + 2 for s in self.voxel_occupancy.shape)
        padded_air = np.ones(padded_shape, dtype=bool)
        padded_air[1:-1, 1:-1, 1:-1] = self.voxel_occupancy == 0

        # Label connected components of air (6-connectivity)
        structure_6conn = np.array([
            [[0, 0, 0], [0, 1, 0], [0, 0, 0]],
            [[0, 1, 0], [1, 1, 1], [0, 1, 0]],
            [[0, 0, 0], [0, 1, 0], [0, 0, 0]],
        ], dtype=bool)
        labels, _ = label(padded_air, structure=structure_6conn)
        exterior_label = labels[0, 0, 0]  # corner is always outside

        exterior_padded = labels == exterior_label
        return exterior_padded[1:-1, 1:-1, 1:-1]

    def _is_brick_interior(self, brick: Brick, exterior_mask: np.ndarray) -> bool:
        """
        Check if a brick is interior (not adjacent to exterior air).

        Args:
            brick: The brick to check.
            exterior_mask: Precomputed boolean array (world_dim³), True = exterior air.

        Returns:
            True if brick is interior (not visible from outside).
        """
        neighbors = [(-1,0,0), (1,0,0), (0,-1,0), (0,1,0), (0,0,-1), (0,0,1)]

        for x in range(brick.x, brick.x + brick.h):
            for y in range(brick.y, brick.y + brick.w):
                z = brick.z
                for dx, dy, dz in neighbors:
                    nx, ny, nz = x + dx, y + dy, z + dz
                    if (0 <= nx < self.world_dim and
                        0 <= ny < self.world_dim and
                        0 <= nz < self.world_dim):
                        if exterior_mask[nx, ny, nz]:
                            return False
                    else:
                        return False

        return True

    def remove_interior_deferred_bricks(self, deferred_bricks: set[Brick]) -> list[Brick]:
        """
        Remove deferred bricks that are interior (not visible from outside).
        Computes exterior mask once and reuses it for all checks.

        Args:
            deferred_bricks: Set of bricks that were force-placed during reordering

        Returns:
            List of removed bricks
        """
        if not deferred_bricks:
            return []

        exterior_mask = self._compute_exterior_mask()
        removed_bricks = []

        for brick in deferred_bricks:
            if brick not in self.bricks:
                continue

            if self._is_brick_interior(brick, exterior_mask):
                self.voxel_occupancy[brick.slice] -= 1
                self.bricks.remove(brick)
                removed_bricks.append(brick)

        if removed_bricks:
            print(f"  🗑️  Removed {len(removed_bricks)} interior deferred bricks (out of {len(deferred_bricks)} total deferred)")

        return removed_bricks


    def to_ldr(self, save_numpy_path: str = None, reorder_for_stability: bool = True) -> str:
        """
        Convert brick structure to LDR format.
        
        Args:
            save_numpy_path: Optional path to save numpy voxel array before conversion
            reorder_for_stability: If True, reorder bricks to avoid floating parts in steps
        """
        if save_numpy_path:
            self.save_numpy_voxels(save_numpy_path)
            
        if reorder_for_stability:
            ordered_bricks, deferred_bricks = self._reorder_bricks_for_stability(self.bricks)
            
            # Remove interior deferred bricks - they can't be built and aren't visible
            if deferred_bricks:
                print(f"  📊 Found {len(deferred_bricks)} deferred bricks during reordering")
                removed = self.remove_interior_deferred_bricks(deferred_bricks)
                
                # Re-run reordering if we removed bricks
                if removed:
                    ordered_bricks, _ = self._reorder_bricks_for_stability(self.bricks)
            
            # Remove any floating bricks that may have been created by interior removal
            floating_removed = self.remove_floating_bricks()
            if floating_removed:
                # Re-run reordering after removing floating bricks
                ordered_bricks, _ = self._reorder_bricks_for_stability(self.bricks)
        else:
            ordered_bricks = self.bricks
            
        # Generate LDR using brick colors
        ldr_lines = []
        for brick in ordered_bricks:
            # Use the brick's stored color (which may have been set by remove_interior_hanging_bricks for visualization)
            ldr_lines.append(brick.to_ldr(color=brick.color))
            
        return ''.join(ldr_lines)

    def add_brick(self, brick: Brick) -> None:
        self.bricks.append(brick)
        self.voxel_occupancy[brick.slice] += 1

    def undo_add_brick(self) -> None:
        brick = self.bricks[-1]
        self.voxel_occupancy[brick.slice] -= 1
        self.bricks.pop()

    def has_out_of_bounds_bricks(self) -> bool:
        return any(not self.brick_in_bounds(brick) for brick in self.bricks)

    def brick_in_bounds(self, brick: Brick) -> bool:
        return (all(slice_.start >= 0 and slice_.stop <= self.world_dim for slice_ in brick.slice_2d)
                and 0 <= brick.z < self.world_dim)

    def has_collisions(self) -> bool:
        return np.any(self.voxel_occupancy > 1)

    def brick_collides(self, brick: Brick) -> bool:
        return np.any(self.voxel_occupancy[brick.slice])

    def has_floating_bricks(self) -> bool:
        return any(self.brick_floats(brick) for brick in self.bricks)

    def get_floating_bricks(self) -> list[Brick]:
        """Return a list of all floating bricks in the structure."""
        return [brick for brick in self.bricks if self.brick_floats(brick)]

    def remove_floating_bricks(self) -> list[Brick]:
        """
        Remove all floating bricks from the structure iteratively.
        Continues until no floating bricks remain (handles cascade effects).
        Also records the voxel positions in self.problematic_voxels.
        
        Returns:
            List of all removed bricks
        """
        all_removed = []
        iteration = 0
        
        while True:
            floating = self.get_floating_bricks()
            if not floating:
                break
                
            iteration += 1
            print(f"  🎈 Floating brick removal pass {iteration}: found {len(floating)} floating bricks")
            
            for brick in floating:
                # Record all voxel positions from this brick as problematic
                for x in range(brick.x, brick.x + brick.h):
                    for y in range(brick.y, brick.y + brick.w):
                        self.problematic_voxels.append((x, y, brick.z))
                
                self.voxel_occupancy[brick.slice] -= 1
                self.bricks.remove(brick)
                all_removed.append(brick)
        
        if all_removed:
            print(f"  🗑️  Removed {len(all_removed)} total floating bricks in {iteration} pass(es)")
        
        return all_removed

    def brick_floats(self, brick: Brick) -> bool:
        if brick.z == 0:
            return False  # Supported by ground
        if np.any(self.voxel_occupancy[brick.slice_2d[0], brick.slice_2d[1], brick.z - 1]):
            return False  # Supported from below
        if brick.z != self.world_dim - 1 and np.any(
                self.voxel_occupancy[brick.slice_2d[0], brick.slice_2d[1], brick.z + 1]):
            return False  # Supported from above
        return True

    def is_stable(self) -> bool:
        if self.has_floating_bricks() or self.has_collisions():
            return False
        return self.stability_scores().max() < 1

    def stability_scores(self) -> np.ndarray:
        if self.has_collisions():
            raise ValueError('Cannot compute stability scores - structure has colliding bricks.')
        if self.has_out_of_bounds_bricks():
            raise ValueError('Cannot compute stability scores - structure has out of bounds bricks.')
        scores, _, _, _, _ = stability_score(self.to_json(), brick_library,
                                             StabilityConfig(world_dimension=(self.world_dim,) * 3))
        return scores

    @classmethod
    def from_json(cls, bricks_json: dict, world_dim: int = 20):
        bricks = [Brick.from_json(v) for k, v in bricks_json.items() if k.isdigit()]
        return cls(bricks, world_dim=world_dim)

    @classmethod
    def from_txt(cls, bricks_txt: str):
        bricks_txt = bricks_txt.split('\n')
        bricks_txt = [b for b in bricks_txt if b.strip()]  # Remove blank lines
        bricks = [Brick.from_txt(brick) for brick in bricks_txt]
        return cls(bricks)

    @classmethod
    def from_ldr(cls, bricks_ldr: str):
        bricks_ldr = bricks_ldr.split('0 STEP')  # Split on step lines
        bricks_ldr = [b for b in bricks_ldr if b.strip()]  # Remove blank or whitespace-only lines
        bricks = [Brick.from_ldr(brick) for brick in bricks_ldr]
        return cls(bricks)


class ConnectivityBrickStructure:
    """
    Brick structure that keeps graph connectivity information
    """

    def __init__(self, shape: tuple[int, int, int]):
        self.voxel_bricks = np.zeros(shape, dtype=int)  # Which brick occupies each voxel; 0 = no brick
        self.bricks = {}  # Dictionary node_id -> brick
        self.node_id_counter = 0

        self.connection_graph = nx.Graph()
        self.neighbor_graph = nx.Graph()

        self._connected_components = None
        self._component_labels = None
        self._node2component = None

    @property
    def max_x(self) -> int:
        return self.voxel_bricks.shape[0]

    @property
    def max_y(self) -> int:
        return self.voxel_bricks.shape[1]

    @property
    def max_z(self) -> int:
        return self.voxel_bricks.shape[2]

    @property
    def voxels(self) -> np.ndarray:
        return self.voxel_bricks != 0

    def _reset_cache(self) -> None:
        self._connected_components = None
        self._component_labels = None
        self._node2component = None

    def n_components(self) -> int:
        return len(self.connected_components())

    def connected_components(self):
        if self._connected_components is None:
            self._connected_components = list(nx.connected_components(self.connection_graph))
        return self._connected_components

    def component_labels(self) -> np.ndarray:
        if self._component_labels is None:
            self._component_labels = np.zeros_like(self.voxel_bricks)
            for i, comp in enumerate(self.connected_components()):
                for node in comp:
                    brick = self.bricks[node]
                    self._component_labels[brick.slice] = i + 1
        return self._component_labels

    def node2component(self) -> dict[int, int]:
        if self._node2component is None:
            self._node2component = {node: component_idx + 1
                                    for component_idx, component in enumerate(self.connected_components())
                                    for node in component}
        return self._node2component

    def stability_score(self) -> np.ndarray:
        bricks = BrickStructure(list(self.bricks.values()))
        return bricks.stability_scores()

    def node_exists(self, node_id: int):
        return node_id in self.bricks

    def add_brick(self, brick: Brick) -> int:
        self._reset_cache()

        if self.voxel_bricks[brick.slice].any():  # Brick overlaps other bricks on layer
            raise ValueError(f'Cannot place brick {brick} due to collisions')

        self.node_id_counter += 1
        node = self.node_id_counter
        self.bricks[node] = brick
        self.voxel_bricks[brick.slice] = node

        # Update graph edges
        self.connection_graph.add_node(node)
        self.neighbor_graph.add_node(node)
        vert_neighbors = ({(node, self.voxel_bricks[x, y, brick.z - 1])
                           for x in range(brick.x, brick.x + brick.h) for y in range(brick.y, brick.y + brick.w)
                           if brick.z > 0} |
                          {(node, self.voxel_bricks[x, y, brick.z + 1])
                           for x in range(brick.x, brick.x + brick.h) for y in range(brick.y, brick.y + brick.w)
                           if brick.z + 1 < self.max_z})
        vert_neighbors = list(filter(lambda e: e[1] != 0, vert_neighbors))  # Remove connections with empty bricks
        horz_neighbors = ({(node, self.voxel_bricks[brick.x - 1, y, brick.z])
                           for y in range(brick.y, brick.y + brick.w) if brick.x > 0} |
                          {(node, self.voxel_bricks[brick.x + brick.h, y, brick.z])
                           for y in range(brick.y, brick.y + brick.w) if brick.x + brick.h < self.max_x} |
                          {(node, self.voxel_bricks[x, brick.y - 1, brick.z])
                           for x in range(brick.x, brick.x + brick.h) if brick.y > 0} |
                          {(node, self.voxel_bricks[x, brick.y + brick.w, brick.z])
                           for x in range(brick.x, brick.x + brick.h) if brick.y + brick.w < self.max_y})
        horz_neighbors = list(filter(lambda e: e[1] != 0, horz_neighbors))  # Remove connections with empty bricks
        self.connection_graph.add_edges_from(vert_neighbors)
        self.neighbor_graph.add_edges_from(vert_neighbors + horz_neighbors)

        return node

    def add_bricks(self, bricks: list[Brick]) -> list[int]:
        return [self.add_brick(brick) for brick in bricks]

    def remove_brick(self, node_id: int) -> None:
        self._reset_cache()

        brick = self.bricks[node_id]
        self.bricks.pop(node_id)
        self.voxel_bricks[brick.slice] = 0
        self.connection_graph.remove_node(node_id)
        self.neighbor_graph.remove_node(node_id)

    def remove_voxel_subset(self, voxel_subset: np.ndarray) -> list[Brick]:
        """
        Erases all bricks inside the specified subset of voxels.
        Assumes that all bricks in voxel_subset are completely contained within voxel_subset.
        """
        removed_bricks = []
        nodes = set(np.unique(self.voxel_bricks[voxel_subset])) - {0}
        for node in nodes:
            brick = self.bricks[node]
            assert voxel_subset[brick.slice].all()
            removed_bricks.append(brick)
            self.remove_brick(node)
        return removed_bricks
