#!/usr/bin/env python3

import csv
import re
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import open3d as o3d

# Path to the LDR color CSV file
_CSV_PATH = Path(__file__).parent.parent.parent / "gobrick_colors.csv"


def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """
    Convert sRGB color (0-1 range) to CIELAB color space.
    
    CIELAB is perceptually uniform, meaning equal distances in the space
    correspond to equal perceived color differences. This prevents
    near-gray colors from matching tinted colors like pink or aqua.
    
    Args:
        rgb: sRGB values in range [0, 1] (length 3)
        
    Returns:
        CIELAB [L*, a*, b*] array
    """
    # sRGB gamma decode to linear RGB
    linear = np.where(
        rgb > 0.04045,
        ((rgb + 0.055) / 1.055) ** 2.4,
        rgb / 12.92
    )
    
    # Linear RGB to CIE XYZ (D65 illuminant, sRGB primaries)
    matrix = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041]
    ])
    xyz = matrix @ linear
    
    # Normalize by D65 white point
    xyz_ref = np.array([0.95047, 1.0, 1.08883])
    xyz_n = xyz / xyz_ref
    
    # XYZ to CIELAB
    epsilon = 0.008856
    kappa = 903.3
    f = np.where(
        xyz_n > epsilon,
        np.cbrt(xyz_n),
        (kappa * xyz_n + 16.0) / 116.0
    )
    
    L = 116.0 * f[1] - 16.0
    a = 500.0 * (f[0] - f[1])
    b = 200.0 * (f[1] - f[2])
    
    return np.array([L, a, b])


def load_ldr_color_map() -> Dict[int, Tuple[float, float, float]]:
    """
    Load LDR color map from gobrick_colors.csv
    
    Returns:
        Dictionary mapping LDR color codes to RGB tuples (0-1 range)
    """
    print(f"📖 Loading LDR color map from: {_CSV_PATH}")
    
    with open(_CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        color_map = {}
        
        for row in reader:
            # Extract LDraw ID and RGB hex
            ldraw_match = re.match(r'(\d+)', row.get('LDraw', ''))
            rgb_hex = row.get('RGB', '')
            
            if ldraw_match and len(rgb_hex) == 6:
                try:
                    ldraw_id = int(ldraw_match.group(1))
                    # Convert hex to RGB (0-1 range)
                    rgb = tuple(int(rgb_hex[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                    color_map[ldraw_id] = rgb
                except ValueError:
                    continue
        
        print(f"✅ Loaded {len(color_map)} LDR colors from {_CSV_PATH}")
        return color_map


def _precompute_lab_color_map(color_map: Dict[int, Tuple[float, float, float]], excluded_colors: set = None) -> list:
    """
    Pre-compute CIELAB values for all LDR colors to avoid redundant conversions.
    
    Returns:
        List of (color_code, rgb_tuple, lab_array) for each non-excluded color
    """
    if excluded_colors is None:
        excluded_colors = {16, 24}  # 16 = Main Color, 24 = Edge Color (placeholders)
    
    lab_entries = []
    for color_code, ldr_rgb in color_map.items():
        if color_code in excluded_colors:
            continue
        ldr_lab = _srgb_to_lab(np.array(ldr_rgb))
        lab_entries.append((color_code, ldr_rgb, ldr_lab))
    return lab_entries


def rgb_to_ldr_color(rgb_color: np.ndarray, color_map: Dict[int, Tuple[float, float, float]], _lab_cache: list = None) -> Tuple[int, np.ndarray]:
    """
    Convert RGB color (0-1 range) to nearest LDR color code using perceptual
    distance in CIELAB color space (Delta E CIE76).
    
    Using CIELAB instead of raw RGB Euclidean distance prevents near-gray
    colors from incorrectly matching tinted colors like Light Aqua or
    Bright Pink that happen to be numerically close in RGB space.
    
    Args:
        rgb_color: RGB values in range [0, 1]
        color_map: Dictionary mapping LDR color codes to RGB tuples
        _lab_cache: Optional pre-computed LAB values from _precompute_lab_color_map()
        
    Returns:
        Tuple of (LDR color code, LDR RGB values)
    """
    if len(rgb_color) != 3:
        return 7, np.array([0.5, 0.5, 0.5])  # Default to light gray
    
    # Clamp to valid range
    rgb_color = np.clip(rgb_color, 0, 1)
    
    # Convert input to CIELAB
    input_lab = _srgb_to_lab(rgb_color)
    
    # Compute input chroma — low-chroma inputs (grays) need stronger
    # protection against matching to chromatic colors, because the LEGO
    # palette has a large lightness gap between White (L*≈100) and
    # Light Bluish Gray (L*≈68) that lets tinted colors like Light Aqua
    # (L*≈78) sneak in as "nearest" purely on lightness proximity.
    input_chroma = np.sqrt(input_lab[1] ** 2 + input_lab[2] ** 2)
    chroma_threshold = 10.0
    if input_chroma < chroma_threshold:
        # Scale up chroma weight for desaturated inputs (max ≈ 9x at chroma=0)
        chroma_weight = 1.0 + 8.0 * (1.0 - input_chroma / chroma_threshold)
    else:
        chroma_weight = 1.0
    
    # Find closest color using chroma-weighted Delta E in CIELAB space
    min_distance = float('inf')
    closest_color_code = 7  # Default to light gray
    closest_rgb = np.array([0.5, 0.5, 0.5])
    
    if _lab_cache is not None:
        # Use pre-computed LAB values (fast path)
        for color_code, ldr_rgb, ldr_lab in _lab_cache:
            dL = input_lab[0] - ldr_lab[0]
            da = input_lab[1] - ldr_lab[1]
            db = input_lab[2] - ldr_lab[2]
            distance = np.sqrt(dL ** 2 + chroma_weight * (da ** 2 + db ** 2))
            if distance < min_distance:
                min_distance = distance
                closest_color_code = color_code
                closest_rgb = np.array(ldr_rgb)
    else:
        # Compute LAB on the fly (fallback for single-color calls)
        excluded_colors = {16, 24}
        for color_code, ldr_rgb in color_map.items():
            if color_code in excluded_colors:
                continue
            ldr_lab = _srgb_to_lab(np.array(ldr_rgb))
            dL = input_lab[0] - ldr_lab[0]
            da = input_lab[1] - ldr_lab[1]
            db = input_lab[2] - ldr_lab[2]
            distance = np.sqrt(dL ** 2 + chroma_weight * (da ** 2 + db ** 2))
            if distance < min_distance:
                min_distance = distance
                closest_color_code = color_code
                closest_rgb = np.array(ldr_rgb)
    
    return closest_color_code, closest_rgb


def color_array_to_ldr_colors(voxel_array: np.ndarray, color_array: np.ndarray) -> np.ndarray:
    """
    Convert RGB color array to LDR color codes for each voxel.
    
    Args:
        voxel_array: 3D boolean array indicating occupied voxels
        color_array: 3D RGB array with colors for each voxel (values in range [0, 1])
        
    Returns:
        3D array of LDR color codes (integers) for each voxel
    """
    print(f"\n🎨 Converting colors to LDR color codes...")
    
    # Load the LDR color map and pre-compute LAB values
    ldr_color_map = load_ldr_color_map()
    lab_cache = _precompute_lab_color_map(ldr_color_map)
    
    # Create an array to store LDR color codes for each voxel
    ldr_color_array = np.zeros(voxel_array.shape, dtype=int)
    
    # Convert each voxel's RGB color to nearest LDR color code
    occupied_positions = np.where(voxel_array)
    unique_ldr_colors = set()
    
    for x, y, z in zip(*occupied_positions):
        rgb_color = color_array[x, y, z]
        ldr_color_code, _ = rgb_to_ldr_color(rgb_color, ldr_color_map, _lab_cache=lab_cache)
        ldr_color_array[x, y, z] = ldr_color_code
        unique_ldr_colors.add(ldr_color_code)
    
    unique_colors_count = len(unique_ldr_colors)
    print(f"  ✅ Converted {len(occupied_positions[0])} voxels to {unique_colors_count} unique LDR colors")
    
    return ldr_color_array


def convert_xyzrgb_to_ldr_colors(xyzrgb_content: str) -> str:
    """
    Convert xyzrgb content to use nearest LDR colors instead of original RGB values.
    
    Args:
        xyzrgb_content: String content of xyzrgb file (x y z r g b per line, RGB in 0-255)
        
    Returns:
        New xyzrgb content string with colors mapped to nearest LDR colors
    """
    print(f"\n🎨 Converting XYZRGB colors to LDR palette...")
    
    # Load the LDR color map and pre-compute LAB values
    ldr_color_map = load_ldr_color_map()
    lab_cache = _precompute_lab_color_map(ldr_color_map)
    
    lines = xyzrgb_content.strip().split('\n')
    converted_lines = []
    unique_ldr_colors = set()
    
    for line in lines:
        if not line.strip():
            continue
            
        parts = line.split()
        if len(parts) < 6:
            continue
            
        # Parse coordinates and RGB
        x, y, z = parts[0], parts[1], parts[2]
        r, g, b = float(parts[3]), float(parts[4]), float(parts[5])
        
        # Normalize to 0-1 range and find nearest LDR color
        rgb_normalized = np.array([r / 255.0, g / 255.0, b / 255.0])
        ldr_color_code, ldr_rgb = rgb_to_ldr_color(rgb_normalized, ldr_color_map, _lab_cache=lab_cache)
        unique_ldr_colors.add(ldr_color_code)
        
        # Convert LDR RGB back to 0-255 range
        ldr_r = int(ldr_rgb[0] * 255)
        ldr_g = int(ldr_rgb[1] * 255)
        ldr_b = int(ldr_rgb[2] * 255)
        
        converted_lines.append(f"{x} {y} {z} {ldr_r} {ldr_g} {ldr_b}")
    
    print(f"  ✅ Converted {len(converted_lines)} voxels to {len(unique_ldr_colors)} unique LDR colors")
    
    return '\n'.join(converted_lines)