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
  - [Merkle proofs](#merkle-proofs)
- [Presets](#presets)
  - [Execution payload chunks](#execution-payload-chunks)
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
class PayloadChunkData(ByteVector):
    """
    The bytes of a single execution payload chunk.
    """

    LENGTH = PAYLOAD_CHUNK_SIZE
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

| Name                             | Value             | Description                                                  |
| -------------------------------- | ----------------- | ------------------------------------------------------------ |
| `PAYLOAD_CHUNK_FIELD_MODULUS`    | `Uint64(0x1100B)` | Primitive polynomial `x^16 + x^12 + x^3 + x + 1` of GF(2^16) |
| `PAYLOAD_CHUNK_SYMBOL_SIZE`      | `Uint64(2)`       | Bytes per GF(2^16) symbol                                    |
| `PAYLOAD_CHUNK_EXTENSION_FACTOR` | `Uint64(2)`       | Total chunks per data chunk                                  |

### Merkle proofs

| Name                        | Value                                              |
| --------------------------- | -------------------------------------------------- |
| `PAYLOAD_CHUNK_PROOF_DEPTH` | `Uint64(floorlog2(MAX_PAYLOAD_CHUNKS) + 1)` (= 13) |

## Presets

### Execution payload chunks

| Name                 | Value                      |
| -------------------- | -------------------------- |
| `PAYLOAD_CHUNK_SIZE` | `Uint64(2**15)` (= 32,768) |
| `MAX_PAYLOAD_CHUNKS` | `Uint64(2**12)` (= 4,096)  |

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

#### New `get_payload_data_chunk_count`

```python
def get_payload_data_chunk_count(payload_length: Uint64) -> Uint64:
    """
    Return the number of chunks needed to hold a serialized payload of
    ``payload_length`` bytes, the last of which is zero-padded.
    """
    return (payload_length + PAYLOAD_CHUNK_SIZE - 1) // PAYLOAD_CHUNK_SIZE
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

Every chunk of a payload is a codeword of the same Reed-Solomon code. For each
symbol position, the symbols of the chunks are the evaluations at the chunk
indices of a single polynomial over GF(2^16) whose degree is less than the
number of data chunks. Any such number of chunks therefore determines every
other chunk, whether it is a data chunk or a parity chunk.

```python
def compute_payload_chunk(
    known_chunks: Sequence[PayloadChunkData],
    known_indices: Sequence[PayloadChunkIndex],
    index: PayloadChunkIndex,
) -> PayloadChunkData:
    """
    Compute the chunk at ``index`` from the ``known_chunks`` located at
    ``known_indices``, whose count must equal the number of data chunks.
    """
    coefficients = compute_lagrange_coefficients(
        [int(known_index) for known_index in known_indices], int(index)
    )
    chunk = b""
    for offset in range(0, PAYLOAD_CHUNK_SIZE, PAYLOAD_CHUNK_SYMBOL_SIZE):
        symbol = 0
        for i, known_chunk in enumerate(known_chunks):
            known_symbol = int.from_bytes(
                known_chunk[offset : offset + PAYLOAD_CHUNK_SYMBOL_SIZE], ENDIANNESS
            )
            symbol ^= gf16_multiply(coefficients[i], known_symbol)
        chunk += symbol.to_bytes(PAYLOAD_CHUNK_SYMBOL_SIZE, ENDIANNESS)
    return PayloadChunkData(chunk)
```

#### New `compute_payload_chunks`

```python
def compute_payload_chunks(payload_bytes: bytes) -> Sequence[PayloadChunkData]:
    """
    Split ``payload_bytes`` into data chunks, padding the last one with zero
    bytes, and extend them with parity chunks. The code is systematic: the
    data chunks come first and hold the payload bytes verbatim.
    """
    data_chunk_count = get_payload_data_chunk_count(Uint64(len(payload_bytes)))
    chunk_count = get_payload_chunk_count(Uint64(len(payload_bytes)))
    padding = b"\x00" * (data_chunk_count * PAYLOAD_CHUNK_SIZE - len(payload_bytes))
    padded_bytes = payload_bytes + padding

    data_chunks = []
    for i in range(data_chunk_count):
        start = i * PAYLOAD_CHUNK_SIZE
        data_chunks.append(PayloadChunkData(padded_bytes[start : start + PAYLOAD_CHUNK_SIZE]))
    data_indices = [PayloadChunkIndex(i) for i in range(data_chunk_count)]

    parity_chunks = []
    for i in range(data_chunk_count, chunk_count):
        parity_chunks.append(compute_payload_chunk(data_chunks, data_indices, PayloadChunkIndex(i)))
    return data_chunks + parity_chunks
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
    known_chunks = [chunks[index] for index in known_indices]

    payload_bytes = b""
    for i in range(data_chunk_count):
        index = PayloadChunkIndex(i)
        if index in chunks:
            payload_bytes += chunks[index]
        else:
            payload_bytes += compute_payload_chunk(known_chunks, known_indices, index)
    return payload_bytes[:payload_length]
```

#### New `compute_payload_chunks_root`

```python
def compute_payload_chunks_root(chunks: Sequence[PayloadChunkData]) -> Root:
    """
    Return the commitment to ``chunks``: the root of the list of their hashes.
    """
    return hash_tree_root(PayloadChunkHashes(data=[sha256(chunk) for chunk in chunks]))
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
    assert get_payload_chunk_count(bid.payload_length) <= MAX_PAYLOAD_CHUNKS

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
