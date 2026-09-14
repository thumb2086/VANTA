//! MT19937 — 與 CPython `random.Random(int_seed)` 位元級相容
//!
//! CPython `_randommodule.c`：
//!   * int seed → `init_genrand(seed & 0xFFFFFFFF)`（PyLong_AsUnsignedLongMask）
//!   * `random()` → `genrand_res53()` = ((a >> 5) * 67108864.0 + (b >> 6)) / 2^53
//!   * `uniform(a, b)` = a + (b - a) * random()
//! 本實作完全對照，保證相同種子 → 相同浮點序列。

pub struct MT19937 {
    mt: [u32; 624],
    mti: usize,
}

const N: usize = 624;
const M: usize = 397;
const MATRIX_A: u32 = 0x9908b0df;
const UPPER_MASK: u32 = 0x8000_0000;
const LOWER_MASK: u32 = 0x7fff_ffff;

impl MT19937 {
    /// 以 init_by_array([seed], 1) 種子化（numpy 慣例）——與 Python 端
    /// server/core/rng.py 及官方 MT19937 參考實作位元級一致。
    pub fn new(seed: u32) -> Self {
        let mut m = MT19937 { mt: [0u32; N], mti: N };
        m.init_genrand(19650218);
        let key = [seed & 0xffff_ffff];
        let mut i = 1usize;
        let mut j = 0usize;
        let mut k = N.max(key.len());
        while k > 0 {
            let inner = m.mt[i - 1] ^ (m.mt[i - 1] >> 30);
            m.mt[i] = (m.mt[i] ^ inner.wrapping_mul(1664525))
                .wrapping_add(key[j])
                .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= N {
                m.mt[0] = m.mt[N - 1];
                i = 1;
            }
            if j >= key.len() {
                j = 0;
            }
            k -= 1;
        }
        for _ in 0..N - 1 {
            let inner = m.mt[i - 1] ^ (m.mt[i - 1] >> 30);
            m.mt[i] = (m.mt[i] ^ inner.wrapping_mul(1566083941)).wrapping_sub(i as u32);
            i += 1;
            if i >= N {
                m.mt[0] = m.mt[N - 1];
                i = 1;
            }
        }
        m.mt[0] = 0x8000_0000;
        m
    }

    fn init_genrand(&mut self, s: u32) {
        self.mt[0] = s;
        for i in 1..N {
            self.mt[i] = 1812433253u32
                .wrapping_mul(self.mt[i - 1] ^ (self.mt[i - 1] >> 30))
                .wrapping_add(i as u32);
        }
        self.mti = N;
    }

    fn twist(&mut self) {
        for i in 0..N {
            let y = (self.mt[i] & UPPER_MASK) | (self.mt[(i + 1) % N] & LOWER_MASK);
            self.mt[i] = self.mt[(i + M) % N] ^ (y >> 1) ^ (if y & 1 != 0 { MATRIX_A } else { 0 });
        }
        self.mti = 0;
    }

    pub fn gen_int32(&mut self) -> u32 {
        if self.mti >= N {
            self.twist();
        }
        let mut y = self.mt[self.mti];
        self.mti += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c_5680;
        y ^= (y << 15) & 0xefc6_0000;
        y ^= y >> 18;
        y
    }

    /// genrand_res53：Python random.random()
    pub fn random(&mut self) -> f64 {
        let a = (self.gen_int32() >> 5) as f64;
        let b = (self.gen_int32() >> 6) as f64;
        (a * 67108864.0 + b) / 9007199254740992.0
    }

    /// Python random.uniform(lo, hi) = lo + (hi - lo) * random()
    pub fn uniform(&mut self, lo: f64, hi: f64) -> f64 {
        lo + (hi - lo) * self.random()
    }
}
