"""M0 純數學核心單元測試。"""

import math

from server.core.math_core import Vec3, approach, approach_vec, clamp, lerp


def test_vec_basics():
    a = Vec3(1, 2, 3)
    b = Vec3(4, -5, 6)
    assert (a + b) == Vec3(5, -3, 9)
    assert (b - a) == Vec3(3, -7, 3)
    assert (a * 2) == Vec3(2, 4, 6)
    assert (2 * a) == Vec3(2, 4, 6)
    assert (-a) == Vec3(-1, -2, -3)
    assert a.dot(b) == 12
    assert a.cross(b) == Vec3(27, 6, -13)


def test_vec_normalized():
    v = Vec3(3, 0, 4)
    n = v.normalized()
    assert math.isclose(n.length(), 1.0, rel_tol=1e-9)
    assert n == Vec3(0.6, 0, 0.8)
    # 零向量：回傳零向量而非除零
    assert Vec3().normalized() == Vec3()


def test_vec_horizontal():
    v = Vec3(1, 9, 2)
    assert v.horizontal() == Vec3(1, 0, 2)


def test_vec_distance():
    assert Vec3(0, 0, 0).distance_to(Vec3(3, 4, 0)) == 5.0


def test_clamp_lerp_approach():
    assert clamp(5, 0, 3) == 3
    assert clamp(-1, 0, 3) == 0
    assert clamp(2, 0, 3) == 2
    assert lerp(0, 10, 0.5) == 5
    # approach：朝 target 移動但單次不超過 max_delta
    assert approach(0, 10, 3) == 3
    assert approach(9, 10, 3) == 10
    assert approach(0, -10, 3) == -3


def test_approach_vec():
    assert approach_vec(Vec3(0, 0, 0), Vec3(10, 0, 0), 3) == Vec3(3, 0, 0)
    assert approach_vec(Vec3(9, 0, 0), Vec3(10, 0, 0), 3) == Vec3(10, 0, 0)
    # 零向量 target 時不產生 NaN
    assert approach_vec(Vec3(), Vec3(), 3) == Vec3()
