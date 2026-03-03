"""
Image tiling system for shelf analysis.

Splits large overview photos into overlapping tiles to preserve detail
that would be lost when Gemini downscales images. Each tile gets analyzed
as if it were a close-up photo.
"""
from pathlib import Path
from PIL import Image
import math
import os

# Minimum width/height in pixels for a photo to be worth tiling.
# Below this, the image is already close-up enough.
MIN_TILE_DIMENSION = 1500

# Target tile size — each tile will be roughly this many pixels wide/tall.
# Gemini processes images well at ~1500-2000px per dimension.
TARGET_TILE_SIZE = 1200

# Overlap between adjacent tiles as a fraction (0.15 = 15%).
# Ensures products at tile edges aren't cut in half.
OVERLAP_FRACTION = 0.20


def should_tile(image_path: str) -> bool:
    """Check if an image is large enough to benefit from tiling."""
    with Image.open(image_path) as img:
        w, h = img.size
        return w >= MIN_TILE_DIMENSION and h >= MIN_TILE_DIMENSION


def classify_photos(photo_paths: list[str]) -> dict:
    """
    Classify photos into overview vs close-up based on resolution and aspect ratio.
    Returns dict with 'overview' and 'closeup' lists.
    """
    overviews = []
    closeups = []

    for path in photo_paths:
        with Image.open(path) as img:
            w, h = img.size
            megapixels = (w * h) / 1_000_000
            aspect = w / h if h > 0 else 1

            # Heuristic: overview photos tend to be wider and higher resolution
            # Close-ups tend to be more square or portrait, or lower resolution
            is_overview = (
                megapixels >= 2.0 and  # At least 2MP
                (aspect >= 1.3 or megapixels >= 4.0)  # Wide OR very high-res
            )

            if is_overview:
                overviews.append(path)
            else:
                closeups.append(path)

    # If no overviews detected, treat the largest image as overview
    if not overviews and photo_paths:
        sizes = []
        for p in photo_paths:
            with Image.open(p) as img:
                sizes.append((p, img.size[0] * img.size[1]))
        sizes.sort(key=lambda x: x[1], reverse=True)
        overviews.append(sizes[0][0])
        closeups = [p for p in photo_paths if p != sizes[0][0]]

    return {"overview": overviews, "closeup": closeups}


def tile_image(image_path: str, output_dir: str) -> list[dict]:
    """
    Split an image into overlapping tiles.

    Returns a list of dicts with:
      - path: path to the tile image file
      - original: original image filename
      - position: human-readable position (e.g., "top-left", "center")
      - tile_index: sequential index
      - row: row index
      - col: column index
    """
    img = Image.open(image_path)
    w, h = img.size
    original_name = Path(image_path).stem
    ext = Path(image_path).suffix

    # Calculate grid dimensions
    overlap_px_w = int(TARGET_TILE_SIZE * OVERLAP_FRACTION)
    overlap_px_h = int(TARGET_TILE_SIZE * OVERLAP_FRACTION)
    step_w = TARGET_TILE_SIZE - overlap_px_w
    step_h = TARGET_TILE_SIZE - overlap_px_h

    cols = max(1, math.ceil((w - overlap_px_w) / step_w))
    rows = max(1, math.ceil((h - overlap_px_h) / step_h))

    # Recalculate step to distribute evenly
    if cols > 1:
        step_w = (w - TARGET_TILE_SIZE) // (cols - 1)
    if rows > 1:
        step_h = (h - TARGET_TILE_SIZE) // (rows - 1)

    tiles = []
    tile_idx = 0

    for row in range(rows):
        for col in range(cols):
            x1 = min(col * step_w, w - TARGET_TILE_SIZE) if cols > 1 else 0
            y1 = min(row * step_h, h - TARGET_TILE_SIZE) if rows > 1 else 0
            x2 = min(x1 + TARGET_TILE_SIZE, w)
            y2 = min(y1 + TARGET_TILE_SIZE, h)

            # Ensure minimum tile size
            x1 = max(0, x2 - TARGET_TILE_SIZE)
            y1 = max(0, y2 - TARGET_TILE_SIZE)

            tile = img.crop((x1, y1, x2, y2))

            # Determine position label
            position = _get_position_label(row, col, rows, cols)

            tile_filename = f"{original_name}_tile_r{row}_c{col}{ext}"
            tile_path = os.path.join(output_dir, tile_filename)
            tile.save(tile_path, quality=95)

            tiles.append({
                "path": tile_path,
                "original": Path(image_path).name,
                "position": position,
                "tile_index": tile_idx,
                "row": row,
                "col": col,
                "bounds": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            })
            tile_idx += 1

    img.close()
    return tiles


def _get_position_label(row: int, col: int, total_rows: int, total_cols: int) -> str:
    """Generate a human-readable position label for a tile."""
    if total_rows == 1 and total_cols == 1:
        return "full"

    v = "top" if row == 0 else ("bottom" if row == total_rows - 1 else "middle")
    h = "left" if col == 0 else ("right" if col == total_cols - 1 else "center")

    if total_rows == 1:
        return h
    if total_cols == 1:
        return v
    return f"{v}-{h}"


def prepare_images(photo_paths: list[str], session_dir: str) -> dict:
    """
    Main entry point: classify photos and tile overviews.

    Returns:
      {
        "overview_originals": [paths to original overview photos],
        "overview_tiles": [list of tile dicts],
        "closeups": [paths to close-up photos],
        "all_analysis_images": [all images to send for detailed analysis]
      }
    """
    tiles_dir = os.path.join(session_dir, "tiles")
    os.makedirs(tiles_dir, exist_ok=True)

    classified = classify_photos(photo_paths)
    overview_tiles = []

    for overview_path in classified["overview"]:
        if should_tile(overview_path):
            tiles = tile_image(overview_path, tiles_dir)
            overview_tiles.extend(tiles)
        else:
            # Small overview — don't tile, just include as-is
            overview_tiles.append({
                "path": overview_path,
                "original": Path(overview_path).name,
                "position": "full",
                "tile_index": 0,
                "row": 0,
                "col": 0,
            })

    # All images for detailed analysis = tiles + close-ups
    all_analysis = [t["path"] for t in overview_tiles] + classified["closeup"]

    return {
        "overview_originals": classified["overview"],
        "overview_tiles": overview_tiles,
        "closeups": classified["closeup"],
        "all_analysis_images": all_analysis,
    }
