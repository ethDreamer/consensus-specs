# reed-solomon-simd vectors

`vectors.json` holds encodings produced by the `reed-solomon-simd` crate,
version 3.1.0, for several data chunk counts, each with an equal number of
recovery shards. `test_payload_chunks.py` checks that the code defined in the
EIP-8142 specification reproduces them, which shows that the specification's
evaluation points and layout are those computed by additive FFT implementations
over the Cantor basis.

The crate represents field elements by their coordinates in the Cantor basis and
pairs the bytes of a shard into symbols block-wise, so the check translates its
output into the specification's representation before comparing.

Each case gives `original_count`, `shard_bytes`, and the `original` and
`recovery` shards as hex. The originals are pseudo-random bytes. They were
produced with
`reed_solomon_simd::encode(original_count, original_count, original)` by a
throwaway program outside this repository, and any program that feeds the listed
originals to that function reproduces the recovery shards.
