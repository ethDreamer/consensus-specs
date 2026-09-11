# EIP-8142 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `PayloadChunkIndex`](#new-payloadchunkindex)
  - [New `PayloadChunkData`](#new-payloadchunkdata)
  - [New `PayloadChunkHashes`](#new-payloadchunkhashes)
- [Constants](#constants)
  - [Erasure coding](#erasure-coding)
  - [Execution payload chunks](#execution-payload-chunks)
- [Presets](#presets)
  - [Execution payload chunks](#execution-payload-chunks-1)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`ExecutionPayloadContents`](#executionpayloadcontents)
  - [Modified containers](#modified-containers)
    - [`ExecutionPayloadBid`](#executionpayloadbid)
    - [`SignedExecutionPayloadBid`](#signedexecutionpayloadbid)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)
  - [Math](#math)
    - [New `gf16_multiply`](#new-gf16_multiply)
    - [New `gf16_inverse`](#new-gf16_inverse)
    - [New `compute_lagrange_coefficients`](#new-compute_lagrange_coefficients)
  - [Misc](#misc)
    - [New `get_payload_chunk_point`](#new-get_payload_chunk_point)
    - [New `get_payload_chunk_block_size`](#new-get_payload_chunk_block_size)
    - [New `get_payload_chunk_position`](#new-get_payload_chunk_position)
    - [New `get_payload_chunk_size`](#new-get_payload_chunk_size)
    - [New `get_payload_data_chunk_count`](#new-get_payload_data_chunk_count)
    - [New `get_payload_chunk_count`](#new-get_payload_chunk_count)
    - [New `compute_payload_chunk`](#new-compute_payload_chunk)
    - [New `compute_payload_chunks`](#new-compute_payload_chunks)
    - [New `recover_payload_bytes`](#new-recover_payload_bytes)
    - [New `compute_payload_chunks_root`](#new-compute_payload_chunks_root)
    - [New `get_execution_payload_contents`](#new-get_execution_payload_contents)
  - [Predicates](#predicates)
    - [New `is_valid_payload_chunks_root`](#new-is_valid_payload_chunks_root)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Removed `verify_execution_payload_envelope_signature`](#removed-verify_execution_payload_envelope_signature)
    - [Execution payload bid](#execution-payload-bid)
      - [Modified `process_execution_payload_bid`](#modified-process_execution_payload_bid)

<!-- mdformat-toc end -->

## Introduction

This upgrade replaces the dissemination of the execution payload as a single
gossip message with chunked, erasure-coded dissemination. The builder splits the
serialized payload into data chunks, extends them with Reed-Solomon parity
chunks so that any subset of chunks as large as the data recovers the payload,
and commits to the hashes of all chunks in the execution payload bid. Each chunk
travels with a Merkle proof against that commitment, so nodes verify and forward
chunks independently without waiting for the whole payload.

Chunks are `MIN_PAYLOAD_CHUNK_SIZE` bytes until the payload needs more than
`MAX_PAYLOAD_DATA_CHUNKS` of them, beyond which the chunks grow instead of the
chunk count. The number of chunks is therefore bounded, so the erasure code
operates on a fixed maximum size, the number of messages per payload is bounded,
and the work to encode a payload grows linearly with its size.

The bid signature binds the chunk commitment, so the execution payload envelope
no longer carries a signature of its own.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### New `PayloadChunkIndex`

```python
class PayloadChunkIndex(Uint64):
    """
    The position of a chunk within the chunks of an execution payload.
    """
```

### New `PayloadChunkData`

```python
class PayloadChunkData(ByteList):
    """
    The bytes of a single execution payload chunk.
    """

    LIMIT = MAX_PAYLOAD_CHUNK_SIZE
```

### New `PayloadChunkHashes`

```python
class PayloadChunkHashes(List[Bytes32]):
    """
    The hashes of the chunks of an execution payload, in chunk order.
    """

    LIMIT = MAX_PAYLOAD_CHUNKS
```

## Constants

### Erasure coding

| Name                             | Value                                                                                                                              | Description                                                   |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `PAYLOAD_CHUNK_FIELD_MODULUS`    | `Uint64(0x1002D)`                                                                                                                  | Primitive polynomial `x^16 + x^5 + x^3 + x^2 + 1` of GF(2^16) |
| `PAYLOAD_CHUNK_FIELD_BASIS`      | `[0x0001, 0xACCA, 0x3C0E, 0x163E, 0xC582, 0xED2E, 0x914C, 0x4012, 0x6C98, 0x10D8, 0x6A72, 0xB900, 0xFDB8, 0xFB34, 0xFF38, 0x991E]` | Cantor basis of GF(2^16) spanning the evaluation points       |
| `PAYLOAD_CHUNK_SYMBOL_SIZE`      | `Uint64(2)`                                                                                                                        | Bytes per GF(2^16) symbol                                     |
| `PAYLOAD_CHUNK_EXTENSION_FACTOR` | `Uint64(2)`                                                                                                                        | Total chunks per data chunk                                   |

*Note*: `PAYLOAD_CHUNK_FIELD_MODULUS` is the smallest primitive polynomial of
degree 16. `PAYLOAD_CHUNK_FIELD_BASIS` is determined by the modulus: its first
element is `1`, and each later element is the even one of the two roots of
`x^2 + x = c` where `c` is the element before it, the roots differing by `1`.
Elements of GF(2^16) are represented as integers whose bits are the coefficients
of a polynomial over GF(2), and symbols are their little-endian bytes.

### Execution payload chunks

| Name                        | Value                                                                      | Description                              |
| --------------------------- | -------------------------------------------------------------------------- | ---------------------------------------- |
| `MAX_PAYLOAD_CHUNKS`        | `Uint64(PAYLOAD_CHUNK_EXTENSION_FACTOR * MAX_PAYLOAD_DATA_CHUNKS)` (= 128) | Data and parity chunks per payload       |
| `PAYLOAD_CHUNK_PROOF_DEPTH` | `Uint64(floorlog2(MAX_PAYLOAD_CHUNKS) + 1)` (= 8)                          | Depth of a chunk hash in the chunks root |

## Presets

### Execution payload chunks

| Name                      | Value                         | Description                                |
| ------------------------- | ----------------------------- | ------------------------------------------ |
| `MAX_PAYLOAD_DATA_CHUNKS` | `Uint64(2**6)` (= 64)         | Data chunks per payload, once chunks grow  |
| `MIN_PAYLOAD_CHUNK_SIZE`  | `Uint64(2**14)` (= 16,384)    | Chunk size in bytes until the count is hit |
| `MAX_PAYLOAD_CHUNK_SIZE`  | `Uint64(2**20)` (= 1,048,576) | Bound on the chunk size in bytes           |

## Containers

### New containers

#### `ExecutionPayloadContents`

```python
class ExecutionPayloadContents(Container):
    """
    The part of an execution payload envelope that is committed to by the
    bid and disseminated as chunks.
    """

    payload: ExecutionPayload
    execution_requests: ExecutionRequests
```

### Modified containers

#### `ExecutionPayloadBid`

```python
class ExecutionPayloadBid(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=15)

    parent_block_hash: Hash32
    parent_block_root: Root
    block_hash: Hash32
    prev_randao: Bytes32
    fee_recipient: ExecutionAddress
    gas_limit: Uint64
    builder_index: BuilderIndex
    slot: Slot
    value: Gwei
    execution_payment: Gwei
    blob_kzg_commitments: BlobKZGCommitments
    execution_requests_root: Root
    inclusion_list_bits: InclusionListBits
    # [New in EIP8142]
    payload_chunks_root: Root
    # [New in EIP8142]
    payload_length: Uint64
```

#### `SignedExecutionPayloadBid`

```python
class SignedExecutionPayloadBid(Container):
    # [Modified in EIP8142]
    message: ExecutionPayloadBid
    signature: BLSSignature
```

#### `BeaconState`

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=46)

    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: BlockRoots
    state_roots: StateRoots
    historical_roots: HistoricalRoots
    eth1_data: Eth1Data
    eth1_data_votes: Eth1DataVotes
    eth1_deposit_index: Uint64
    validators: Validators
    balances: Balances
    randao_mixes: RandaoMixes
    slashings: Slashings
    previous_epoch_participation: EpochParticipation
    current_epoch_participation: EpochParticipation
    justification_bits: JustificationBits
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: InactivityScores
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    latest_block_hash: Hash32
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: HistoricalSummaries
    deposit_requests_start_index: Uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: PendingDeposits
    pending_partial_withdrawals: PendingPartialWithdrawals
    pending_consolidations: PendingConsolidations
    proposer_lookahead: ProposerLookahead
    builders: Builders
    next_withdrawal_builder_index: BuilderIndex
    execution_payload_availability: ExecutionPayloadAvailability
    builder_pending_payments: BuilderPendingPayments
    builder_pending_withdrawals: BuilderPendingWithdrawals
    # [Modified in EIP8142]
    latest_execution_payload_bid: ExecutionPayloadBid
    payload_expected_withdrawals: Withdrawals
    ptc_window: PayloadTimelinessCommitteeWindow
```

## Helper functions

### Math

#### New `gf16_multiply`

```python
def gf16_multiply(a: int, b: int) -> int:
    """
    Multiply two elements of GF(2^16), represented as integers below ``2**16``
    whose bits are the coefficients of a polynomial over GF(2), modulo
    ``PAYLOAD_CHUNK_FIELD_MODULUS``.
    """
    product = 0
    while b > 0:
        if b & 1:
            product ^= a
        a <<= 1
        if a >= 2**16:
            a ^= PAYLOAD_CHUNK_FIELD_MODULUS
        b >>= 1
    return product
```

#### New `gf16_inverse`

```python
def gf16_inverse(a: int) -> int:
    """
    Return the multiplicative inverse of the non-zero GF(2^16) element ``a``,
    which is ``a`` raised to the power ``2**16 - 2``.
    """
    result = 1
    base = a
    exponent = 2**16 - 2
    while exponent > 0:
        if exponent & 1:
            result = gf16_multiply(result, base)
        base = gf16_multiply(base, base)
        exponent >>= 1
    return result
```

#### New `compute_lagrange_coefficients`

```python
def compute_lagrange_coefficients(points: Sequence[int], target: int) -> Sequence[int]:
    """
    Return the coefficients ``c`` such that, for every polynomial ``p`` over
    GF(2^16) of degree less than ``len(points)``, ``p(target)`` is the sum of
    ``c[i] * p(points[i])``. Addition in GF(2^16) is XOR, so subtraction is
    too.
    """
    coefficients = []
    for i, point in enumerate(points):
        numerator = 1
        denominator = 1
        for j, other in enumerate(points):
            if i != j:
                numerator = gf16_multiply(numerator, target ^ other)
                denominator = gf16_multiply(denominator, point ^ other)
        coefficients.append(gf16_multiply(numerator, gf16_inverse(denominator)))
    return coefficients
```

### Misc

#### New `get_payload_chunk_point`

```python
def get_payload_chunk_point(position: Uint64) -> int:
    """
    Return the evaluation point at ``position``: the sum of the elements of
    ``PAYLOAD_CHUNK_FIELD_BASIS`` selected by the bits of ``position``. The
    points at positions below a power of two form a subspace of GF(2^16),
    and the points at the next as many positions form its coset.
    """
    point = 0
    for bit, basis_element in enumerate(PAYLOAD_CHUNK_FIELD_BASIS):
        if (position >> bit) & 1:
            point ^= basis_element
    return point
```

#### New `get_payload_chunk_block_size`

```python
def get_payload_chunk_block_size(data_chunk_count: Uint64) -> Uint64:
    """
    Return the number of positions the data chunks are laid out over: the
    smallest power of two that is at least ``data_chunk_count``.
    """
    return Uint64(2 ** ceillog2(data_chunk_count))
```

#### New `get_payload_chunk_position`

```python
def get_payload_chunk_position(index: PayloadChunkIndex, data_chunk_count: Uint64) -> Uint64:
    """
    Return the position of the evaluation point of the chunk at ``index``.
    Data chunks take the positions from the block size upwards, and parity
    chunks the positions from zero upwards.
    """
    block_size = get_payload_chunk_block_size(data_chunk_count)
    if index < data_chunk_count:
        return block_size + index
    return index - data_chunk_count
```

#### New `get_payload_chunk_size`

```python
def get_payload_chunk_size(payload_length: Uint64) -> Uint64:
    """
    Return the chunk size for a serialized payload of ``payload_length``
    bytes. Chunks are ``MIN_PAYLOAD_CHUNK_SIZE`` bytes unless the payload
    would then need more than ``MAX_PAYLOAD_DATA_CHUNKS`` of them, in which
    case they grow to hold it in that many. Chunks hold whole symbols, so
    the size is rounded up to a multiple of ``PAYLOAD_CHUNK_SYMBOL_SIZE``.
    """
    chunk_size = max(
        MIN_PAYLOAD_CHUNK_SIZE,
        (payload_length + MAX_PAYLOAD_DATA_CHUNKS - 1) // MAX_PAYLOAD_DATA_CHUNKS,
    )
    remainder = chunk_size % PAYLOAD_CHUNK_SYMBOL_SIZE
    if remainder != 0:
        chunk_size += PAYLOAD_CHUNK_SYMBOL_SIZE - remainder
    return chunk_size
```

#### New `get_payload_data_chunk_count`

```python
def get_payload_data_chunk_count(payload_length: Uint64) -> Uint64:
    """
    Return the number of chunks needed to hold a serialized payload of
    ``payload_length`` bytes, the last of which is zero-padded. This is at
    most ``MAX_PAYLOAD_DATA_CHUNKS``.
    """
    chunk_size = get_payload_chunk_size(payload_length)
    return (payload_length + chunk_size - 1) // chunk_size
```

#### New `get_payload_chunk_count`

```python
def get_payload_chunk_count(payload_length: Uint64) -> Uint64:
    """
    Return the total number of chunks, data and parity, that a serialized
    payload of ``payload_length`` bytes is disseminated as.
    """
    return get_payload_data_chunk_count(payload_length) * PAYLOAD_CHUNK_EXTENSION_FACTOR
```

#### New `compute_payload_chunk`

For each symbol position, the symbols of the chunks of a payload are the
evaluations of a single polynomial over GF(2^16) at the chunks' points. With
`block_size` the block size of the data chunk count, the polynomial has degree
below `block_size`. It is determined by the data chunks together with zero
chunks at the positions left in the block, so any `block_size` evaluations
determine every other one, the zero chunks always being among the known ones.

*Note*: The data chunks lie on a coset of the subspace spanned by the first
`log2(block_size)` basis elements and the parity chunks on the subspace itself,
so implementations may evaluate and interpolate with additive fast Fourier
transforms over the Cantor basis. Implementations that represent field elements
by their coordinates in `PAYLOAD_CHUNK_FIELD_BASIS`, as such transforms do,
translate every symbol with a lookup table each way; the chunks and their
commitment are always over the representation defined here.

```python
def compute_payload_chunk(
    known_chunks: Dict[PayloadChunkIndex, PayloadChunkData],
    data_chunk_count: Uint64,
    index: PayloadChunkIndex,
) -> PayloadChunkData:
    """
    Compute the chunk at ``index`` from ``known_chunks``, which must hold
    exactly ``data_chunk_count`` chunks.
    """
    assert len(known_chunks) == data_chunk_count
    block_size = get_payload_chunk_block_size(data_chunk_count)

    # The known evaluations are the known chunks and the zero chunks in the block
    known_indices = sorted(known_chunks.keys())
    points = [
        get_payload_chunk_point(get_payload_chunk_position(known_index, data_chunk_count))
        for known_index in known_indices
    ]
    for position in range(block_size + data_chunk_count, 2 * block_size):
        points.append(get_payload_chunk_point(Uint64(position)))
    target = get_payload_chunk_point(get_payload_chunk_position(index, data_chunk_count))
    # Zero chunks contribute nothing, so only the coefficients of the known chunks are used
    coefficients = compute_lagrange_coefficients(points, target)

    chunk_size = len(known_chunks[known_indices[0]])
    chunk = b""
    for offset in range(0, chunk_size, PAYLOAD_CHUNK_SYMBOL_SIZE):
        symbol = 0
        for i, known_index in enumerate(known_indices):
            known_symbol = int.from_bytes(
                known_chunks[known_index][offset : offset + PAYLOAD_CHUNK_SYMBOL_SIZE], ENDIANNESS
            )
            symbol ^= gf16_multiply(coefficients[i], known_symbol)
        chunk += symbol.to_bytes(PAYLOAD_CHUNK_SYMBOL_SIZE, ENDIANNESS)
    return PayloadChunkData(data=chunk)
```

#### New `compute_payload_chunks`

```python
def compute_payload_chunks(payload_bytes: bytes) -> Sequence[PayloadChunkData]:
    """
    Split ``payload_bytes`` into data chunks, padding the last one with zero
    bytes, and extend them with parity chunks. The code is systematic: the
    data chunks come first and hold the payload bytes verbatim.
    """
    payload_length = Uint64(len(payload_bytes))
    chunk_size = get_payload_chunk_size(payload_length)
    data_chunk_count = get_payload_data_chunk_count(payload_length)
    chunk_count = get_payload_chunk_count(payload_length)
    padding = b"\x00" * (data_chunk_count * chunk_size - len(payload_bytes))
    padded_bytes = payload_bytes + padding

    data_chunks = {}
    for i in range(data_chunk_count):
        start = i * chunk_size
        data_chunks[PayloadChunkIndex(i)] = PayloadChunkData(
            data=padded_bytes[start : start + chunk_size]
        )

    chunks = [data_chunks[PayloadChunkIndex(i)] for i in range(data_chunk_count)]
    for i in range(data_chunk_count, chunk_count):
        chunks.append(compute_payload_chunk(data_chunks, data_chunk_count, PayloadChunkIndex(i)))
    return chunks
```

#### New `recover_payload_bytes`

```python
def recover_payload_bytes(
    chunks: Dict[PayloadChunkIndex, PayloadChunkData], payload_length: Uint64
) -> bytes:
    """
    Recover a serialized payload of ``payload_length`` bytes from ``chunks``,
    which must hold at least as many chunks as there are data chunks.
    """
    data_chunk_count = get_payload_data_chunk_count(payload_length)
    assert len(chunks) >= data_chunk_count

    known_indices = sorted(chunks.keys())[:data_chunk_count]
    known_chunks = {index: chunks[index] for index in known_indices}

    payload_bytes = b""
    for i in range(data_chunk_count):
        index = PayloadChunkIndex(i)
        if index in chunks:
            payload_bytes += bytes(chunks[index])
        else:
            payload_bytes += bytes(compute_payload_chunk(known_chunks, data_chunk_count, index))
    return payload_bytes[:payload_length]
```

#### New `compute_payload_chunks_root`

```python
def compute_payload_chunks_root(chunks: Sequence[PayloadChunkData]) -> Root:
    """
    Return the commitment to ``chunks``: the root of the list of their hashes.
    """
    return hash_tree_root(PayloadChunkHashes(data=[sha256(bytes(chunk)) for chunk in chunks]))
```

#### New `get_execution_payload_contents`

```python
def get_execution_payload_contents(
    envelope: ExecutionPayloadEnvelope,
) -> ExecutionPayloadContents:
    return ExecutionPayloadContents(
        payload=envelope.payload,
        execution_requests=envelope.execution_requests,
    )
```

### Predicates

#### New `is_valid_payload_chunks_root`

```python
def is_valid_payload_chunks_root(bid: ExecutionPayloadBid, payload_bytes: bytes) -> bool:
    """
    Check whether ``payload_bytes`` is the serialized payload that ``bid``
    commits to through its payload length and chunks root.
    """
    if len(payload_bytes) != bid.payload_length:
        return False
    chunks = compute_payload_chunks(payload_bytes)
    return compute_payload_chunks_root(chunks) == bid.payload_chunks_root
```

## Beacon chain state transition function

### Block processing

#### Execution payload

##### Removed `verify_execution_payload_envelope_signature`

The execution payload envelope is no longer signed. Its authenticity follows
from `is_valid_payload_chunks_root`, since the bid that commits to the chunks
root is signed by the builder and included in the beacon block.

#### Execution payload bid

##### Modified `process_execution_payload_bid`

```python
def process_execution_payload_bid(
    state: BeaconState, signed_bid: SignedExecutionPayloadBid
) -> None:
    bid = signed_bid.message
    builder_index = bid.builder_index
    amount = bid.value

    # For self-builds, amount must be zero regardless of withdrawal credential prefix
    if builder_index == BUILDER_INDEX_SELF_BUILD:
        assert amount == 0
        assert signed_bid.signature == bls.G2_POINT_AT_INFINITY
    else:
        # Verify that the builder is active
        assert is_active_builder(state, builder_index)
        # Verify that the builder is a payload builder
        assert state.builders[builder_index].version == PAYLOAD_BUILDER_VERSION
        # Verify that the builder has funds to cover the bid
        assert can_builder_cover_bid(state, builder_index, amount)
        # Verify that the bid signature is valid
        assert verify_execution_payload_bid_signature(state, signed_bid)

    # Verify commitments are under limit
    assert (
        len(bid.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )

    # [New in EIP8142]
    # Verify that the committed payload can be disseminated as chunks
    assert bid.payload_length > 0
    assert get_payload_chunk_size(bid.payload_length) <= MAX_PAYLOAD_CHUNK_SIZE

    # Verify that the bid is for the current slot
    assert bid.slot == state.slot
    assert state.slot > GENESIS_SLOT
    # Verify that the bid is for the right parent block
    assert bid.parent_block_hash == state.latest_block_hash
    # Verify that the bid's block hash differs from its parent block hash
    assert bid.block_hash != bid.parent_block_hash
    assert bid.parent_block_root == get_block_root_at_slot(state, state.slot - 1)
    assert bid.prev_randao == get_randao_mix(state, get_current_epoch(state))

    # Record the pending payment if there is some payment
    if amount > 0:
        pending_payment = BuilderPendingPayment(
            weight=Gwei(0),
            withdrawal=BuilderPendingWithdrawal(
                fee_recipient=bid.fee_recipient,
                amount=amount,
                builder_index=builder_index,
            ),
            proposer_index=get_beacon_proposer_index(state),
        )
        state.builder_pending_payments[SLOTS_PER_EPOCH + bid.slot % SLOTS_PER_EPOCH] = (
            pending_payment
        )

    # Cache the signed execution payload bid
    state.latest_execution_payload_bid = bid
```
