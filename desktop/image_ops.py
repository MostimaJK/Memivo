"""Pixel-identical preview blending with bounded temporary arrays."""
import numpy as np


def segmentation_overlay(original, mask, rows=128):
    overlay = np.asarray(original).copy()
    color = np.array([48, 114, 235])
    # Preserve the original float64 arithmetic and truncation exactly. Only the
    # temporary selection/blend buffers are bounded, not the output image.
    for top in range(0, overlay.shape[0], rows):
        block = overlay[top:top + rows]
        selected = mask[top:top + rows]
        block[selected] = (block[selected] * .3 + color * .7).astype(np.uint8)
    return overlay
