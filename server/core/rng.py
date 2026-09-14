"""
server/core/rng.py — 確定性 RNG（跨語言可對齊）
================================================
純 Python 的 MT19937 實作，與 Rust 端（rust/parity/src/mt19937.rs）位元級一致：
  * 種子：init_by_array([seed_u32], 1)（numpy 慣例）
  * random()：genrand_res53
  * uniform(a, b) = a + (b-a) * random()
用途：
  * 黃金資料產生（recoil 等）——讓 Python 與 Rust 的隨機序列 100% 一致
  * 正式遊戲若需「Python↔Rust 雙軌」也可逐步替換 random.Random
參考：MT19937 原論文 / CPython _randommodule.c / numpy RandomState
"""

from __future__ import annotations

N = 624
M = 397
MATRIX_A = 0x9908B0DF
UPPER_MASK = 0x80000000
LOWER_MASK = 0x7FFFFFFF


class MT19937:
    def __init__(self, seed: int):
        self.mt = [0] * N
        self._init_by_array([seed & 0xFFFFFFFF])

    # ------------------------------------------------------------------ #
    def _init_genrand(self, s: int) -> None:
        self.mt[0] = s & 0xFFFFFFFF
        for i in range(1, N):
            self.mt[i] = (1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i) & 0xFFFFFFFF
        self.mti = N

    def _init_by_array(self, key: list[int]) -> None:
        self._init_genrand(19650218)
        i, j = 1, 0
        k = max(N, len(key))
        for _ in range(k):
            self.mt[i] = ((self.mt[i] ^ ((self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) * 1664525))
                          + key[j] + j) & 0xFFFFFFFF
            i += 1
            j += 1
            if i >= N:
                self.mt[0] = self.mt[N - 1]
                i = 1
            if j >= len(key):
                j = 0
        for _ in range(N - 1):
            self.mt[i] = ((self.mt[i] ^ ((self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) * 1566083941))
                          - i) & 0xFFFFFFFF
            i += 1
            if i >= N:
                self.mt[0] = self.mt[N - 1]
                i = 1
        self.mt[0] = 0x80000000

    # ------------------------------------------------------------------ #
    def _twist(self) -> None:
        for i in range(N):
            y = (self.mt[i] & UPPER_MASK) | (self.mt[(i + 1) % N] & LOWER_MASK)
            self.mt[i] = self.mt[(i + M) % N] ^ (y >> 1) ^ (MATRIX_A if y & 1 else 0)
        self.mti = 0

    def gen_int32(self) -> int:
        if self.mti >= N:
            self._twist()
        y = self.mt[self.mti]
        self.mti += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18
        return y & 0xFFFFFFFF

    def random(self) -> float:
        a = self.gen_int32() >> 5
        b = self.gen_int32() >> 6
        return (a * 67108864.0 + b) / 9007199254740992.0

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.random()
