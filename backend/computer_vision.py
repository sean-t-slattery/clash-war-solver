"""Calibrated image reconstruction; synthetic detection is an explicit test mode."""
import cv2
import numpy as np

from backend.domain import Structure
from backend.fixtures import ANCHORS, PALETTE


def decode_image(raw: bytes):
    if len(raw) > 12*1024*1024: raise ValueError("Maximum upload size is 12 MB")
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None: raise ValueError("Upload a decodable PNG, JPEG or WebP image")
    if image.shape[0]*image.shape[1] > 24_000_000:
        raise ValueError("Maximum decoded image size is 24 megapixels")
    return image


def pixel_to_grid(points, anchors):
    origin, a, b = np.array(anchors, dtype=float)
    matrix = np.column_stack(((a-origin)/44, (b-origin)/44))
    if abs(np.linalg.det(matrix)) < .01: raise ValueError("Invalid isometric calibration")
    return np.linalg.solve(matrix, (np.asarray(points).reshape(-1, 2)-origin).T).T


def reconstruct(image, mode="manual", anchors=None):
    if mode == "synthetic":
        if image.shape[:2] != (500, 960):
            raise ValueError("Synthetic mode requires the bundled 960×500 fixture")
        anchors = ANCHORS
    if mode == "manual" or anchors is None:
        return {"structures": [], "anchors": anchors, "warnings": ["No trained game detector is installed. Calibrate three grid corners and reconstruct manually, or request uncertain contour proposals."]}
    structures = []
    if mode == "synthetic":
        for kind, color in PALETTE.items():
            mask = cv2.inRange(image, np.array(color, np.uint8), np.array(color, np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                if cv2.contourArea(contour) < 8: continue
                grid = pixel_to_grid(contour[:, 0], anchors)
                x, y = np.rint(grid.min(axis=0)).astype(int)
                width, height = np.rint(grid.max(axis=0)-[x, y]).astype(int)
                width, height = max(1, width), max(1, height)
                if x < 0 or y < 0 or x+width > 44 or y+height > 44: continue
                if kind == "wall":
                    # Rasterized adjacent one-tile walls can form one contour.
                    # Split only tiles whose centers carry the fixture wall color.
                    origin, ax, ay = np.array(anchors)
                    for wx in range(x, x+width):
                        for wy in range(y, y+height):
                            px, py = np.rint(origin+(ax-origin)*(wx+.5)/44+(ay-origin)*(wy+.5)/44).astype(int)
                            if np.array_equal(image[py, px], np.array(color, np.uint8)):
                                structures.append(Structure(type=kind, x=int(wx), y=int(wy), width=1, height=1,
                                                            reviewed=False, confidence=.99, source="synthetic_palette_detector").model_dump())
                    continue
                structures.append(Structure(type=kind, x=int(x), y=int(y), width=int(width), height=int(height),
                                            reviewed=False, confidence=.99, source="synthetic_palette_detector").model_dump())
        if not structures: raise ValueError("No synthetic fixture colors were found")
        warnings = ["Synthetic palette recognition only. Review detections before solving; this is not a real-game detector."]
    elif mode == "contours":
        edges = cv2.Canny(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 70, 160)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        occupied = set()
        for contour in sorted(contours, key=cv2.contourArea, reverse=True):
            if not 40 <= cv2.contourArea(contour) <= 10000: continue
            moment = cv2.moments(contour)
            if not moment["m00"]: continue
            point = pixel_to_grid([[moment["m10"]/moment["m00"], moment["m01"]/moment["m00"]]], anchors)[0]
            x, y = int(round(point[0]-1.5)), int(round(point[1]-1.5))
            cells = {(i, j) for i in range(x, x+3) for j in range(y, y+3)}
            if x < 0 or y < 0 or x > 41 or y > 41 or occupied & cells: continue
            occupied |= cells
            structures.append(Structure(type="unknown", x=x, y=y, confidence=.2, reviewed=False,
                                        source="unclassified_contour").model_dump())
            if len(structures) >= 150: break
        warnings = ["Contour proposals are unclassified, may be UI decorations, and have no calibrated detection confidence. Reclassify or remove every proposal."]
    else:
        raise ValueError("Unknown reconstruction mode")
    return {"structures": structures, "anchors": anchors, "warnings": warnings}
