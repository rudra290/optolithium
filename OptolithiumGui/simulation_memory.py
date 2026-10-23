"""Shared memory estimates for the numerical simulation backend."""

import os


MEBIBYTE = 1024 * 1024
AERIAL_WORKER_MEMORY_BUDGET_BYTES = 256 * MEBIBYTE
MAPPED_CUBE_THRESHOLD_BYTES = (64 * MEBIBYTE if os.name != "nt" else (1 << 63) - 1)
MAPPED_VOLUME_WORKING_SET_BYTES = 128 * MEBIBYTE
REFLECTION_CACHE_ENTRY_LIMIT = 8192

# The native cache stores a tree node and an allocated complex vector per entry.
# This deliberately overestimates their combined allocator overhead.
REFLECTION_CACHE_ENTRY_ESTIMATED_BYTES = 256
AERIAL_WORKER_MATRIX_BYTES_PER_CELL = 24  # complex field (16) + intensity (8)


def estimate_aerial_worker_count(n_rows, n_cols, work_items=None, hardware_threads=None,
                                 with_reflection_cache=False):
    if hardware_threads is None:
        hardware_threads = os.cpu_count() or 1

    plane_cells = max(1, int(n_rows) * int(n_cols))
    bytes_per_worker = plane_cells * AERIAL_WORKER_MATRIX_BYTES_PER_CELL
    if with_reflection_cache:
        bytes_per_worker += (2 * REFLECTION_CACHE_ENTRY_LIMIT *
                             REFLECTION_CACHE_ENTRY_ESTIMATED_BYTES)

    workers_by_memory = max(1, AERIAL_WORKER_MEMORY_BUDGET_BYTES // bytes_per_worker)
    worker_count = max(1, min(int(hardware_threads), int(workers_by_memory)))
    if work_items is not None:
        worker_count = min(worker_count, max(1, int(work_items)))
    return worker_count


def estimate_aerial_worker_memory_bytes(n_rows, n_cols, work_items=None,
                                        with_reflection_cache=False):
    worker_count = estimate_aerial_worker_count(
        n_rows, n_cols, work_items=work_items,
        with_reflection_cache=with_reflection_cache)
    plane_cells = max(1, int(n_rows) * int(n_cols))
    bytes_per_worker = plane_cells * AERIAL_WORKER_MATRIX_BYTES_PER_CELL
    if with_reflection_cache:
        bytes_per_worker += (2 * REFLECTION_CACHE_ENTRY_LIMIT *
                             REFLECTION_CACHE_ENTRY_ESTIMATED_BYTES)
    return worker_count * bytes_per_worker


def estimate_resist_grid(pitch_x, pitch_y, thickness, grid_xy, grid_z):
    """Return conservative X, Y, and Z voxel counts for a resist volume."""
    nx = max(1, int(pitch_x / grid_xy) + 4)
    ny = max(1, int(pitch_y / grid_xy) + 4)
    nz = max(1, int(thickness / grid_z) + 3)
    return nx, ny, nz


def estimate_volume_resident_bytes(volume_bytes):
    """Estimate RAM for a volume stage with file-backed arrays enabled."""
    if volume_bytes < MAPPED_CUBE_THRESHOLD_BYTES:
        return int(volume_bytes)
    return MAPPED_VOLUME_WORKING_SET_BYTES
