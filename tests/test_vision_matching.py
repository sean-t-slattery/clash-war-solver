import cv2
import numpy as np
import pytest

from backend.base_matching import fingerprint, match
from backend.computer_vision import decode_image, pixel_to_grid, reconstruct
from backend.domain import Layout
from backend.fixtures import ANCHORS, render_fixture


def test_fixture_detection_coordinates_and_classification(layout, tmp_path):
    image_path = tmp_path / "fixture.png"
    render_fixture(layout, image_path)
    detected = reconstruct(decode_image(image_path.read_bytes()), "synthetic")
    prediction = Layout(structures=detected["structures"])
    # Exact type, footprint, level and coordinate agreement on the synthetic image.
    assert fingerprint(prediction) == fingerprint(layout)
    assert all(not s.reviewed for s in prediction.structures)
    assert len(prediction.structures) == len(layout.structures)


def test_real_image_never_fabricates_classifications():
    image = np.zeros((300, 500, 3), dtype=np.uint8)
    cv2.rectangle(image, (200, 100), (230, 130), (255, 255, 255), 3)
    result = reconstruct(image, "manual")
    assert result["structures"] == []
    assert "No trained" in result["warnings"][0]


def test_grid_affine_round_trip():
    points = np.array([ANCHORS[0], ANCHORS[1], ANCHORS[2], (480, 238)])
    assert np.allclose(pixel_to_grid(points, ANCHORS), [[0, 0], [44, 0], [0, 44], [22, 22]])


def test_invalid_image_and_wrong_synthetic_mode():
    with pytest.raises(ValueError): decode_image(b"not an image")
    with pytest.raises(ValueError): reconstruct(np.zeros((200, 200, 3), dtype=np.uint8), "synthetic")


def test_rotated_layout_exact(layout):
    copy = layout.model_copy(deep=True)
    for s in copy.structures:
        s.x, s.y, s.width, s.height = 44-s.y-s.height, s.x, s.height, s.width
    assert fingerprint(copy) == fingerprint(layout)
    assert match(layout, copy)["classification"] == "visible_layout_exact"


def test_modified_layout_is_not_exact(layout):
    copy = layout.model_copy(deep=True)
    copy.structures[1].x += 1
    result = match(layout, copy)
    assert result["classification"] == "near_match"
    assert result["score"] < 1


def test_levels_and_missing_walls_affect_match(layout):
    copy = layout.model_copy(deep=True)
    copy.structures[0].level += 1
    assert match(layout, copy)["classification"] != "visible_layout_exact"
    copy.structures = copy.structures[:8]
    assert match(layout, copy)["score"] < .8
