import numpy as np
import pytest

from src.data.brick_library import (
    brick_id_to_dimensions,
    brick_id_to_part_id,
    dimensions_to_brick_id,
    part_id_to_brick_id,
)
from src.data.brick_structure import Brick, BrickStructure, ConnectivityBrickStructure


def test_brick_library_converts_dimensions_and_ids_both_ways():
    brick_id = dimensions_to_brick_id(2, 1)
    assert dimensions_to_brick_id(1, 2) == brick_id
    assert set(brick_id_to_dimensions(brick_id)) == {1, 2}
    assert part_id_to_brick_id(brick_id_to_part_id(brick_id)) == brick_id
    with pytest.raises(ValueError, match="No brick ID"):
        dimensions_to_brick_id(99, 99)
    with pytest.raises(ValueError, match="No brick ID"):
        part_id_to_brick_id("missing.dat")


def test_brick_properties_and_serialization_round_trip():
    brick = Brick(h=1, w=2, x=2, y=3, z=1, color=14)
    assert brick.area == 2
    assert brick.ori == 0
    assert brick.slice == (slice(2, 3), slice(3, 5), 1)
    assert Brick.from_json(brick.to_json()) == Brick(h=1, w=2, x=2, y=3, z=1)
    assert Brick.from_txt(brick.to_txt()) == Brick(h=1, w=2, x=2, y=3, z=1)
    assert Brick.from_ldr(brick.to_ldr(color=14).split("0 STEP")[0]) == Brick(h=1, w=2, x=2, y=3, z=1)
    with pytest.raises(ValueError, match="ill-formatted"):
        Brick.from_txt("not a brick")
    with pytest.raises(ValueError, match="transformation matrix"):
        Brick.from_ldr("1 4 0 0 0 1 1 1 1 1 1 1 1 1 3004.dat")


def test_structure_detects_bounds_collisions_and_floating_bricks():
    ground = Brick(h=1, w=2, x=1, y=1, z=0)
    supported = Brick(h=1, w=1, x=1, y=1, z=1)
    floating = Brick(h=1, w=1, x=4, y=4, z=2)
    structure = BrickStructure([ground, supported, floating], world_dim=6)
    assert structure.has_floating_bricks()
    assert structure.get_floating_bricks() == [floating]
    assert structure.remove_floating_bricks() == [floating]
    assert structure.problematic_voxels == [(4, 4, 2)]
    assert not structure.has_floating_bricks()

    colliding = BrickStructure([ground, ground], world_dim=6)
    assert colliding.has_collisions()
    assert colliding.brick_collides(ground)
    assert BrickStructure([Brick(h=1, w=1, x=6, y=0, z=0)], world_dim=6).has_out_of_bounds_bricks()


def test_structure_formats_round_trip_and_mutation(tmp_path):
    bricks = [Brick(h=1, w=1, x=0, y=0, z=0), Brick(h=1, w=2, x=1, y=0, z=0)]
    structure = BrickStructure(bricks)
    assert len(structure) == 2
    assert BrickStructure.from_json(structure.to_json()) == structure
    assert BrickStructure.from_txt(structure.to_txt()) == structure
    assert BrickStructure.from_ldr(structure.to_ldr(reorder_for_stability=False)) == structure
    path = tmp_path / "voxels.npy"
    structure.save_numpy_voxels(path)
    assert np.array_equal(np.load(path), structure.voxel_occupancy)
    structure.undo_add_brick()
    assert len(structure) == 1


def test_connectivity_structure_tracks_components_neighbors_and_removal():
    graph = ConnectivityBrickStructure((5, 5, 5))
    bottom, top, separate = (
        Brick(h=1, w=1, x=0, y=0, z=0),
        Brick(h=1, w=1, x=0, y=0, z=1),
        Brick(h=1, w=1, x=4, y=4, z=0),
    )
    nodes = graph.add_bricks([bottom, top, separate])
    assert graph.n_components() == 2
    assert graph.node_exists(nodes[0])
    assert graph.node2component()[nodes[0]] == graph.node2component()[nodes[1]]
    assert graph.component_labels()[0, 0, 0] == graph.component_labels()[0, 0, 1]
    with pytest.raises(ValueError, match="collisions"):
        graph.add_brick(bottom)
    mask = np.zeros((5, 5, 5), dtype=bool)
    mask[4, 4, 0] = True
    assert graph.remove_voxel_subset(mask) == [separate]
    assert graph.n_components() == 1
