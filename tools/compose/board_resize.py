"""Pure geometry for teacher frame handles, in logical canvas units."""
from __future__ import annotations

import math


HANDLES = {'nw': (0, 0), 'n': (.5, 0), 'ne': (1, 0), 'e': (1, .5),
           'se': (1, 1), 's': (.5, 1), 'sw': (0, 1), 'w': (0, .5)}
MIN_SIZE, MAX_SIZE = .1, 100000


def local_to_scene(value, point):
    angle = math.radians(value.get('rotation', 0))
    cosine, sine = math.cos(angle), math.sin(angle)
    return (value['x'] + point[0]*cosine-point[1]*sine,
            value['y'] + point[0]*sine+point[1]*cosine)


def handle_positions(value):
    return {key: local_to_scene(value, (fx*value['width'], fy*value['height']))
            for key, (fx, fy) in HANDLES.items()}


def resize_frame(value, handle, scene_point, *, keep_aspect=False):
    """Keep the opposite handle fixed; sides grow symmetrically when locked.

    Crossing the opposite edge stops at the minimum size instead of flipping.
    The original displayed ratio is retained, including for rotated frames.
    """
    fx, fy = HANDLES[handle]
    width, height = value['width'], value['height']
    angle = math.radians(value.get('rotation', 0))
    cosine, sine = math.cos(angle), math.sin(angle)
    dx, dy = scene_point[0]-value['x'], scene_point[1]-value['y']
    px, py = dx*cosine+dy*sine, -dx*sine+dy*cosine
    ax, ay = (1-fx)*width, (1-fy)*height
    sx = width if fx == .5 else (px-ax)*(1 if fx == 1 else -1)
    sy = height if fy == .5 else (py-ay)*(1 if fy == 1 else -1)
    if keep_aspect:
        if fx == .5:
            scale = sy/height
        elif fy == .5:
            scale = sx/width
        else:
            # Project onto the original diagonal for smooth proportional dragging.
            scale = (sx*width+sy*height)/(width*width+height*height)
        scale = max(max(MIN_SIZE/width, MIN_SIZE/height),
                    min(min(MAX_SIZE/width, MAX_SIZE/height), scale))
        new_width, new_height = width*scale, height*scale
    else:
        new_width = max(MIN_SIZE, min(MAX_SIZE, sx))
        new_height = max(MIN_SIZE, min(MAX_SIZE, sy))
    left, top = ax-(1-fx)*new_width, ay-(1-fy)*new_height
    x, y = local_to_scene(value, (left, top))
    # The model bounds positions too. Refuse an out-of-range preview rather than
    # changing the fixed anchor or presenting a geometry that cannot be saved.
    if not (-100000 <= x <= 100000 and -100000 <= y <= 100000):
        return {key: value[key] for key in ('x', 'y', 'width', 'height')}
    return dict(x=x, y=y, width=new_width, height=new_height)
