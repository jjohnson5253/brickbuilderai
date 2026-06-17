from utils.brick_ids import non_reduced_class_id_to_brick_id


def convert_unconditional_npy_to_ldr(npy_data, ldr_path, color, num_rotations, rotation_id_to_array):
    """Write an unconditional model's output array to an LDR file.

    Args:
        npy_data: Array of shape ``(N, 5)`` where each row is ``(x, y, z, rot_id, brick_class_id)``.
        ldr_path: Output ``.ldr`` file path.
        color: LEGO color code (e.g. ``15`` for white).
        num_rotations: Number of rotation classes (used to validate indices).
        rotation_id_to_array: Mapping from rotation id to a length-9 list of ints
            (row-major 3x3 rotation matrix). Typically loaded from the tokenizer's
            ``id_to_rotation`` dictionary.
    """
    with open(ldr_path, "w") as f:
        for row in npy_data:
            rotation_id = int(row[3])
            assert 0 <= rotation_id < num_rotations, (
                f"Invalid rotation id {rotation_id} (num_rotations={num_rotations})"
            )
            rotation_str = " ".join(str(int(v)) for v in rotation_id_to_array[rotation_id])
            brick_class_id = int(row[4])
            brick_type = non_reduced_class_id_to_brick_id[brick_class_id][0] + ".dat"
            f.write("0 STEP\n")
            f.write(f"1 {color} {row[0]} {-row[1]} {row[2]} {rotation_str} {brick_type}\n")
        f.write("0 STEP\n")
