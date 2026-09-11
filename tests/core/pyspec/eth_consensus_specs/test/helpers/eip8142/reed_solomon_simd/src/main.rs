//! Dump reed-solomon-simd encodings for the EIP-8142 compatibility check.
//!
//! For each case, `original_count` random shards of `shard_bytes` bytes are
//! encoded with an equal number of recovery shards, and everything is written
//! as hex to stdout as JSON. Shards are given to the crate exactly as they are
//! generated: the crate pairs bytes into GF(2^16) symbols in its own layout,
//! and the check on the Python side accounts for that.
use std::fmt::Write;

fn hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        write!(s, "{b:02x}").unwrap();
    }
    s
}

// Small deterministic PRNG so the vectors are reproducible without deps.
struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u8 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        (self.0 >> 24) as u8
    }
}

fn main() {
    let cases: &[(usize, usize)] = &[
        (1, 2),
        (2, 2),
        (3, 4),
        (4, 6),
        (5, 64),
        (7, 66),
        (8, 64),
        (13, 130),
        (31, 64),
        (64, 64),
    ];
    let mut rng = Rng(0x8142_0000_2026_0911);
    let mut out = String::from("[\n");
    for (i, &(k, shard_bytes)) in cases.iter().enumerate() {
        let original: Vec<Vec<u8>> = (0..k)
            .map(|_| (0..shard_bytes).map(|_| rng.next()).collect())
            .collect();
        let recovery = reed_solomon_simd::encode(k, k, &original).expect("encode");
        assert_eq!(recovery.len(), k);
        let orig_hex: Vec<String> = original.iter().map(|s| format!("\"{}\"", hex(s))).collect();
        let rec_hex: Vec<String> = recovery.iter().map(|s| format!("\"{}\"", hex(s))).collect();
        write!(
            out,
            "  {{\"original_count\": {k}, \"shard_bytes\": {shard_bytes}, \"original\": [{}], \"recovery\": [{}]}}{}\n",
            orig_hex.join(", "),
            rec_hex.join(", "),
            if i + 1 == cases.len() { "" } else { "," }
        )
        .unwrap();
    }
    out.push_str("]\n");
    print!("{out}");
}
