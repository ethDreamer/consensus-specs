import json
import random
from itertools import pairwise
from pathlib import Path

from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_eip8142_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL


def _random_payload_bytes(spec, rng, data_chunk_count, short_by=1):
    """
    Random bytes filling ``data_chunk_count`` chunks of the minimum size, the
    last one partially. ``data_chunk_count`` must not exceed the cap.
    """
    assert data_chunk_count <= spec.MAX_PAYLOAD_DATA_CHUNKS
    length = data_chunk_count * spec.MIN_PAYLOAD_CHUNK_SIZE - short_by
    return bytes(rng.getrandbits(8) for _ in range(length))


def _chunks_by_index(spec, chunks, indices):
    return {spec.PayloadChunkIndex(index): chunks[index] for index in indices}


@with_eip8142_and_later
@spec_test
@single_phase
def test_gf16_arithmetic(spec):
    rng = random.Random(1234)
    for _ in range(100):
        a = rng.randrange(1, 2**16)
        b = rng.randrange(1, 2**16)
        # Multiplication is commutative and one is the identity
        assert spec.gf16_multiply(a, b) == spec.gf16_multiply(b, a)
        assert spec.gf16_multiply(a, 1) == a
        # Every non-zero element has an inverse
        assert spec.gf16_multiply(a, spec.gf16_inverse(a)) == 1
        assert spec.gf16_multiply(a, b) < 2**16
    assert spec.gf16_multiply(0, 12345) == 0


@with_eip8142_and_later
@spec_test
@single_phase
def test_payload_chunk_field_basis(spec):
    """
    The basis follows its rule: it starts at one, and each element is the even
    root of ``x^2 + x = previous``.
    """
    basis = spec.PAYLOAD_CHUNK_FIELD_BASIS
    assert len(basis) == 16
    assert basis[0] == 1
    for previous, element in pairwise(basis):
        assert element % 2 == 0
        assert spec.gf16_multiply(element, element) ^ element == previous


@with_eip8142_and_later
@spec_test
@single_phase
def test_payload_chunk_points_form_subspaces(spec):
    """
    The points at positions below a power of two are closed under addition,
    and the next as many positions are a coset of them.
    """
    for log_size in range(1, 5):
        size = 2**log_size
        subspace = {spec.get_payload_chunk_point(spec.Uint64(p)) for p in range(size)}
        assert len(subspace) == size
        assert all(a ^ b in subspace for a in subspace for b in subspace)
        coset = {spec.get_payload_chunk_point(spec.Uint64(size + p)) for p in range(size)}
        assert len(coset) == size
        assert not subspace & coset
        offset = spec.get_payload_chunk_point(spec.Uint64(size))
        assert {point ^ offset for point in subspace} == coset


@with_eip8142_and_later
@spec_test
@single_phase
def test_payload_chunk_positions_are_distinct(spec):
    """
    Every chunk of a payload, data or parity, has its own position, and the
    zero chunks fill the rest of the block.
    """
    for data_chunk_count in range(1, spec.MAX_PAYLOAD_DATA_CHUNKS + 1):
        data_chunk_count = spec.Uint64(data_chunk_count)
        chunk_count = data_chunk_count * spec.PAYLOAD_CHUNK_EXTENSION_FACTOR
        block_size = spec.get_payload_chunk_block_size(data_chunk_count)
        positions = {
            spec.get_payload_chunk_position(spec.PayloadChunkIndex(index), data_chunk_count)
            for index in range(chunk_count)
        }
        assert len(positions) == chunk_count
        zero_positions = set(range(block_size + data_chunk_count, 2 * block_size))
        assert not positions & zero_positions
        assert positions | zero_positions <= set(range(2 * block_size))


def _crate_symbols(shard):
    """
    Symbols as reed-solomon-simd pairs the bytes of a shard: per 64-byte
    block, the low bytes then the high bytes, and likewise for the tail.
    """
    symbols = []
    full = len(shard) // 64 * 64
    for block in range(0, full, 64):
        for i in range(32):
            symbols.append(shard[block + i] | shard[block + 32 + i] << 8)
    tail = shard[full:]
    half = len(tail) // 2
    for i in range(half):
        symbols.append(tail[i] | tail[half + i] << 8)
    return symbols


def _crate_shard_to_chunk(spec, shard):
    """
    Translate a crate shard into a chunk: its symbols are coordinates in
    the Cantor basis, the specification's are polynomial-basis elements.
    """
    chunk = b""
    for coordinates in _crate_symbols(shard):
        element = spec.get_payload_chunk_point(spec.Uint64(coordinates))
        chunk += element.to_bytes(spec.PAYLOAD_CHUNK_SYMBOL_SIZE, spec.ENDIANNESS)
    return spec.PayloadChunkData(data=chunk)


@with_eip8142_and_later
@spec_test
@single_phase
def test_reed_solomon_simd_vectors(spec):
    """
    The specification's code reproduces the parity chunks computed by the
    reed-solomon-simd crate, see ``helpers/eip8142/reed_solomon_simd``.
    """
    vectors_path = (
        Path(__file__).parents[2] / "helpers" / "eip8142" / "reed_solomon_simd" / "vectors.json"
    )
    vectors = json.loads(vectors_path.read_text())
    assert len(vectors) >= 10
    for case in vectors:
        data_chunk_count = spec.Uint64(case["original_count"])
        data_chunks = {
            spec.PayloadChunkIndex(i): _crate_shard_to_chunk(spec, bytes.fromhex(shard))
            for i, shard in enumerate(case["original"])
        }
        for i, shard in enumerate(case["recovery"]):
            expected = _crate_shard_to_chunk(spec, bytes.fromhex(shard))
            index = spec.PayloadChunkIndex(data_chunk_count + i)
            assert spec.compute_payload_chunk(data_chunks, data_chunk_count, index) == expected


@with_eip8142_and_later
@spec_test
@single_phase
def test_lagrange_coefficients_interpolate(spec):
    """
    The coefficients reproduce a polynomial's evaluation at the target from
    its evaluations at the points.
    """
    rng = random.Random(5678)
    degree = 5
    polynomial = [rng.randrange(2**16) for _ in range(degree + 1)]

    def evaluate(x):
        result = 0
        power = 1
        for coefficient in polynomial:
            result ^= spec.gf16_multiply(coefficient, power)
            power = spec.gf16_multiply(power, x)
        return result

    points = list(range(degree + 1))
    for target in range(20):
        coefficients = spec.compute_lagrange_coefficients(points, target)
        interpolated = 0
        for coefficient, point in zip(coefficients, points, strict=True):
            interpolated ^= spec.gf16_multiply(coefficient, evaluate(point))
        assert interpolated == evaluate(target)


@with_eip8142_and_later
@spec_test
@single_phase
def test_get_payload_chunk_size(spec):
    cap = spec.MAX_PAYLOAD_DATA_CHUNKS
    floor = spec.MIN_PAYLOAD_CHUNK_SIZE

    # Below the cap, chunks stay at the floor and the count grows
    for length in [1, floor, floor + 1, cap * floor]:
        assert spec.get_payload_chunk_size(length) == floor
        assert spec.get_payload_data_chunk_count(length) == (length + floor - 1) // floor
    assert spec.get_payload_data_chunk_count(cap * floor) == cap

    # Past the cap, the count stays at the cap and the chunks grow
    for length in [cap * floor + 1, 2 * cap * floor, 3 * cap * floor + 7]:
        chunk_size = spec.get_payload_chunk_size(length)
        assert chunk_size > floor
        assert chunk_size % spec.PAYLOAD_CHUNK_SYMBOL_SIZE == 0
        assert spec.get_payload_data_chunk_count(length) == cap
        assert cap * chunk_size >= length
        assert cap * (chunk_size - spec.PAYLOAD_CHUNK_SYMBOL_SIZE) < length

    # The extension doubles the count either way
    assert spec.get_payload_chunk_count(floor) == 2
    assert spec.get_payload_chunk_count(2 * cap * floor) == spec.MAX_PAYLOAD_CHUNKS


@with_eip8142_and_later
@with_presets([MINIMAL], reason="encoding a payload past the cap is slow in pure Python")
@spec_test
@single_phase
def test_compute_payload_chunks_grown_chunks(spec):
    """Past the cap, the code runs on larger chunks and still recovers."""
    rng = random.Random(9)
    cap = spec.MAX_PAYLOAD_DATA_CHUNKS
    length = cap * spec.MIN_PAYLOAD_CHUNK_SIZE + 5
    payload_bytes = bytes(rng.getrandbits(8) for _ in range(length))
    chunks = spec.compute_payload_chunks(payload_bytes)

    assert len(chunks) == spec.MAX_PAYLOAD_CHUNKS
    assert all(len(chunk) == spec.get_payload_chunk_size(length) for chunk in chunks)
    known = _chunks_by_index(spec, chunks, rng.sample(range(len(chunks)), cap))
    assert spec.recover_payload_bytes(known, spec.Uint64(length)) == payload_bytes


@with_eip8142_and_later
@spec_test
@single_phase
def test_compute_payload_chunks_is_systematic(spec):
    rng = random.Random(1)
    payload_bytes = _random_payload_bytes(spec, rng, data_chunk_count=3)
    chunks = spec.compute_payload_chunks(payload_bytes)

    assert len(chunks) == spec.get_payload_chunk_count(len(payload_bytes))
    assert b"".join(bytes(chunk) for chunk in chunks[:3]).startswith(payload_bytes)
    # The last data chunk is zero padded
    assert b"".join(bytes(chunk) for chunk in chunks[:3])[len(payload_bytes) :] == b"\x00"


@with_eip8142_and_later
@spec_test
@single_phase
def test_recover_payload_bytes_from_any_subset(spec):
    rng = random.Random(2)
    data_chunk_count = 4
    payload_bytes = _random_payload_bytes(spec, rng, data_chunk_count, short_by=17)
    chunks = spec.compute_payload_chunks(payload_bytes)
    payload_length = spec.Uint64(len(payload_bytes))

    # All data chunks, all parity chunks, and mixed subsets
    subsets = [
        list(range(data_chunk_count)),
        list(range(data_chunk_count, 2 * data_chunk_count)),
    ]
    for _ in range(10):
        subsets.append(rng.sample(range(len(chunks)), data_chunk_count))
    for subset in subsets:
        known = _chunks_by_index(spec, chunks, subset)
        assert spec.recover_payload_bytes(known, payload_length) == payload_bytes

    # More chunks than needed also work
    known = _chunks_by_index(spec, chunks, rng.sample(range(len(chunks)), data_chunk_count + 2))
    assert spec.recover_payload_bytes(known, payload_length) == payload_bytes


@with_eip8142_and_later
@spec_test
@single_phase
def test_recover_payload_bytes_too_few_chunks(spec):
    rng = random.Random(3)
    data_chunk_count = 3
    payload_bytes = _random_payload_bytes(spec, rng, data_chunk_count)
    chunks = spec.compute_payload_chunks(payload_bytes)
    known = _chunks_by_index(spec, chunks, [0, 5])

    try:
        spec.recover_payload_bytes(known, spec.Uint64(len(payload_bytes)))
        raise Exception("recovery should fail with too few chunks")
    except AssertionError:
        pass


@with_eip8142_and_later
@spec_test
@single_phase
def test_payload_chunks_root_detects_corruption(spec):
    rng = random.Random(4)
    payload_bytes = _random_payload_bytes(spec, rng, data_chunk_count=2)
    chunks = spec.compute_payload_chunks(payload_bytes)
    root = spec.compute_payload_chunks_root(chunks)

    corrupted = list(chunks)
    corrupted[-1] = spec.PayloadChunkData(data=bytes(len(chunks[-1])))
    assert spec.compute_payload_chunks_root(corrupted) != root

    # The root commits to the chunk count as well
    assert spec.compute_payload_chunks_root(chunks[:-1]) != root


@with_eip8142_and_later
@spec_test
@single_phase
def test_is_valid_payload_chunks_root(spec):
    payload = spec.ExecutionPayload(extra_data=spec.ExtraData(data=[1, 2, 3]))
    contents = spec.ExecutionPayloadContents(
        payload=payload, execution_requests=spec.ExecutionRequests()
    )
    payload_bytes = spec.ssz_serialize(contents)
    bid = spec.ExecutionPayloadBid(
        payload_chunks_root=spec.compute_payload_chunks_root(
            spec.compute_payload_chunks(payload_bytes)
        ),
        payload_length=spec.Uint64(len(payload_bytes)),
    )
    assert spec.is_valid_payload_chunks_root(bid, payload_bytes)

    # Any change to the contents breaks the commitment
    other = contents.copy()
    other.payload.gas_limit = spec.Uint64(1)
    assert not spec.is_valid_payload_chunks_root(bid, spec.ssz_serialize(other))

    # As does a wrong length, even with the right root
    bid.payload_length = spec.Uint64(len(payload_bytes) - 1)
    assert not spec.is_valid_payload_chunks_root(bid, payload_bytes)
