# reed-solomon-simd vectors

`vectors.json` holds encodings produced by the `reed-solomon-simd` crate for
several data chunk counts. `test_payload_chunks.py` checks that the code defined
in the EIP-8142 specification reproduces them, which shows that the
specification's evaluation points and layout are those computed by additive FFT
implementations over the Cantor basis.

The crate represents field elements by their coordinates in the Cantor basis and
pairs the bytes of a shard into symbols block-wise, so the check translates its
output into the specification's representation before comparing.

Regenerate the vectors with:

```
cargo run --release > vectors.json
```
