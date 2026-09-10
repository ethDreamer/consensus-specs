# EIP-8142 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Presets](#presets)
  - [Type-specific SSZ bounds](#type-specific-ssz-bounds)
- [Types](#types)
  - [New `PayloadChunkProof`](#new-payloadchunkproof)
  - [New `ExecutionPayloadEnvelopes`](#new-executionpayloadenvelopes)
- [Containers](#containers)
  - [New `ExecutionPayloadChunk`](#new-executionpayloadchunk)
- [Helpers](#helpers)
  - [Modified `Seen`](#modified-seen)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [New `verify_execution_payload_chunk_proof`](#new-verify_execution_payload_chunk_proof)
  - [New `reconstruct_execution_payload_envelope`](#new-reconstruct_execution_payload_envelope)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [Removed `execution_payload`](#removed-execution_payload)
      - [Modified `execution_payload_bid`](#modified-execution_payload_bid)
      - [New `execution_payload_chunk`](#new-execution_payload_chunk)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
    - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
    - [ExecutionPayloadEnvelopesByRange v1](#executionpayloadenvelopesbyrange-v1)
    - [ExecutionPayloadEnvelopesByRoot v1](#executionpayloadenvelopesbyroot-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8142.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Presets

### Type-specific SSZ bounds

| Name                                            | Value                         |
| ----------------------------------------------- | ----------------------------- |
| `MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE_EIP8142` | `Uint64(196974)` (= ~192 KiB) |

## Types

### New `PayloadChunkProof`

```python
class PayloadChunkProof(Vector[Bytes32]):
    """
    The Merkle proof of a chunk's hash against the chunks root committed to
    by the bid.
    """

    LENGTH = PAYLOAD_CHUNK_PROOF_DEPTH
```

### New `ExecutionPayloadEnvelopes`

```python
class ExecutionPayloadEnvelopes(List[ExecutionPayloadEnvelope]):
    """
    Execution payload envelopes returned in an
    ``ExecutionPayloadEnvelopesByRange`` or
    ``ExecutionPayloadEnvelopesByRoot`` response.
    """

    LIMIT = MAX_REQUEST_PAYLOADS
```

## Containers

### New `ExecutionPayloadChunk`

```python
class ExecutionPayloadChunk(Container):
    beacon_block_root: Root
    slot: Slot
    index: PayloadChunkIndex
    data: PayloadChunkData
    proof: PayloadChunkProof
```

## Helpers

### Modified `Seen`

```python
@dataclass
class Seen:
    proposer_slots: Set[Tuple[Slot, ValidatorIndex]]
    aggregator_epochs: Set[Tuple[Epoch, ValidatorIndex]]
    aggregate_data_roots: Dict[Tuple[Root, CommitteeIndex], Set[Tuple[bool, ...]]]
    voluntary_exit_indices: Set[ValidatorIndex]
    proposer_slashing_indices: Set[ValidatorIndex]
    attester_slashing_indices: Set[ValidatorIndex]
    attestation_validator_epochs: Set[Tuple[Epoch, ValidatorIndex]]
    sync_contribution_aggregator_slots: Set[Tuple[Slot, ValidatorIndex, Uint64]]
    sync_contribution_data: Dict[Tuple[Slot, Root, Uint64], Set[Tuple[bool, ...]]]
    sync_message_validator_slots: Set[Tuple[Slot, ValidatorIndex, Uint64]]
    bls_to_execution_change_indices: Set[ValidatorIndex]
    data_column_sidecar_tuples: Set[Tuple[Root, ColumnIndex]]
    execution_payloads: Dict[Hash32, ExecutionPayload]
    # [Modified in EIP8142]
    # Removed `execution_payload_envelopes`
    # [New in EIP8142]
    execution_payload_chunks: Dict[Root, Dict[PayloadChunkIndex, PayloadChunkData]]
    payload_attestation_validators: Set[Tuple[Slot, ValidatorIndex]]
    execution_payload_bids: Set[Tuple[Slot, Hash32, Root, BuilderIndex]]
    best_execution_payload_bid: Dict[Tuple[Slot, Hash32, Root], Gwei]
    proposer_preferences: Dict[Tuple[Slot, Root], ProposerPreferences]
```

### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8142_FORK_EPOCH:
        return EIP8142_FORK_VERSION
    if epoch >= HEZE_FORK_EPOCH:
        return HEZE_FORK_VERSION
    if epoch >= GLOAS_FORK_EPOCH:
        return GLOAS_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

### New `verify_execution_payload_chunk_proof`

```python
def verify_execution_payload_chunk_proof(
    chunk: ExecutionPayloadChunk, payload_chunks_root: Root
) -> bool:
    """
    Verify that the hash of ``chunk.data`` is the ``chunk.index``-th chunk
    hash committed to by ``payload_chunks_root``.
    """
    gindex = get_subtree_index(get_generalized_index(PayloadChunkHashes, chunk.index))
    return is_valid_merkle_branch(
        leaf=sha256(chunk.data),
        branch=chunk.proof,
        depth=PAYLOAD_CHUNK_PROOF_DEPTH,
        index=gindex,
        root=payload_chunks_root,
    )
```

### New `reconstruct_execution_payload_envelope`

*Note*: The chunks root check makes reconstruction independent of which chunks
were received. If the builder published chunks that are not a consistent
codeword, every honest node fails this check, whichever chunks it holds. If any
node passes it, the committed chunks are all determined by the recovered bytes,
so every node recovers those same bytes, and either all deserialize them or none
does.

```python
def reconstruct_execution_payload_envelope(
    seen: Seen, store: Store, beacon_block_root: Root
) -> ExecutionPayloadEnvelope:
    """
    Reconstruct the execution payload envelope of the block with root
    ``beacon_block_root`` from the chunks seen for it, which must number at
    least as many as there are data chunks.
    """
    block = store.blocks[beacon_block_root]
    bid = block.body.signed_execution_payload_bid.message
    chunks = seen.execution_payload_chunks[beacon_block_root]

    payload_bytes = recover_payload_bytes(chunks, bid.payload_length)
    assert is_valid_payload_chunks_root(bid, payload_bytes)
    contents = ssz_deserialize(ExecutionPayloadContents, payload_bytes)

    # Record the payload, as validating a gossiped envelope used to
    seen.execution_payloads[contents.payload.block_hash] = contents.payload

    return ExecutionPayloadEnvelope(
        payload=contents.payload,
        execution_requests=contents.execution_requests,
        builder_index=bid.builder_index,
        beacon_block_root=beacon_block_root,
        parent_beacon_block_root=block.parent_root,
    )
```

## The gossip domain: gossipsub

### Topics and messages

The `execution_payload_bid` topic is modified to support EIP-8142 bids.

The `execution_payload` topic is removed. Execution payloads are instead
propagated as chunks on the `execution_payload_chunk` topic.

The new topics along with the type of the `data` field of a gossipsub message
are given in this table:

| Name                      | Message Type            |
| ------------------------- | ----------------------- |
| `execution_payload_chunk` | `ExecutionPayloadChunk` |

#### Global topics

##### Removed `execution_payload`

Nodes no longer subscribe to the `execution_payload` topic. Whole envelopes are
only exchanged through the Req/Resp domain.

##### Modified `execution_payload_bid`

The following validations are added, assuming the alias
`bid = signed_execution_payload_bid.message`:

- _[REJECT]_ The bid commits to a payload that can be disseminated as chunks --
  i.e. validate that `bid.payload_length > 0` and
  `get_payload_chunk_count(bid.payload_length) <= MAX_PAYLOAD_CHUNKS`.

##### New `execution_payload_chunk`

This topic is used to propagate chunks of execution payloads as
`ExecutionPayloadChunk`. A chunk is forwarded as soon as it is validated, before
the payload it belongs to is reconstructed.

```python
def validate_execution_payload_chunk_gossip(
    seen: Seen,
    store: Store,
    chunk: ExecutionPayloadChunk,
    current_time_ms: Uint64,
) -> None:
    """
    Validate an ExecutionPayloadChunk for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    block_root = chunk.beacon_block_root

    # [IGNORE] This is the first chunk seen for this block root and index
    seen_chunks = seen.execution_payload_chunks.get(block_root, {})
    if chunk.index in seen_chunks:
        raise GossipIgnore("already seen chunk for this block root and index")

    # [IGNORE] The chunk is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if is_future_slot(store, chunk.slot, current_time_ms):
        raise GossipIgnore("chunk is from a future slot")

    # [IGNORE] The chunk's block root has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if block_root not in store.blocks:
        raise GossipIgnore("chunk's block has not been seen")

    # [REJECT] The chunk's block passes validation
    if block_root not in store.block_states:
        raise GossipReject("chunk's block failed validation")

    # [IGNORE] The chunk is from a slot greater than or equal to the latest finalized slot
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    if chunk.slot < finalized_slot:
        raise GossipIgnore("chunk is from a slot before the latest finalized slot")

    # [IGNORE] The payload for the chunk's block has not been verified yet
    # (it may have been reconstructed already, or retrieved whole)
    if is_payload_verified(store, block_root):
        raise GossipIgnore("payload for chunk's block is already verified")

    block = store.blocks[block_root]

    # [REJECT] The chunk's slot matches the slot of the block
    if chunk.slot != block.slot:
        raise GossipReject("chunk's slot does not match block's slot")

    bid = block.body.signed_execution_payload_bid.message

    # [REJECT] The chunk's index is within the chunk count committed to by the bid
    if chunk.index >= get_payload_chunk_count(bid.payload_length):
        raise GossipReject("chunk's index is out of range")

    # [REJECT] The chunk's proof is valid against the chunks root committed to by the bid
    if not verify_execution_payload_chunk_proof(chunk, bid.payload_chunks_root):
        raise GossipReject("invalid chunk proof")

    # Mark this chunk as seen and keep its data for reconstruction
    if block_root not in seen.execution_payload_chunks:
        seen.execution_payload_chunks[block_root] = {}
    seen.execution_payload_chunks[block_root][chunk.index] = chunk.data
```

Once the node holds `get_payload_data_chunk_count(bid.payload_length)` valid
chunks for a block root, it MUST reconstruct the execution payload envelope with
`reconstruct_execution_payload_envelope` and pass the result to
`on_execution_payload_envelope`. If reconstruction fails, the payload is
invalid: the node MUST NOT retry with other chunks, since the outcome does not
depend on which chunks were received, and it SHOULD ignore further chunks for
that block root.

Chunks for a block root MAY be discarded once its payload is verified, once its
block is orphaned, or once its slot is finalized. Chunks that arrive before
their block MAY be queued, subject to per-peer and per-slot limits.

*Note*: With the default preset, the first `get_payload_data_chunk_count` chunks
hold the serialized payload verbatim, so a node that receives every data chunk
needs no decoding to reconstruct the payload.

## The Req/Resp domain

### Messages

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The EIP-8142 fork-digest is introduced to the `context` enum to specify EIP-8142
beacon block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `FULU_FORK_VERSION`      | `fulu.SignedBeaconBlock`      |
| `GLOAS_FORK_VERSION`     | `gloas.SignedBeaconBlock`     |
| `HEZE_FORK_VERSION`      | `heze.SignedBeaconBlock`      |
| `EIP8142_FORK_VERSION`   | `eip8142.SignedBeaconBlock`   |

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

The EIP-8142 fork-digest is introduced to the `context` enum to specify EIP-8142
beacon block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `FULU_FORK_VERSION`      | `fulu.SignedBeaconBlock`      |
| `GLOAS_FORK_VERSION`     | `gloas.SignedBeaconBlock`     |
| `HEZE_FORK_VERSION`      | `heze.SignedBeaconBlock`      |
| `EIP8142_FORK_VERSION`   | `eip8142.SignedBeaconBlock`   |

#### ExecutionPayloadEnvelopesByRange v1

**Protocol ID:**
`/eth2/beacon_chain/req/execution_payload_envelopes_by_range/1/`

Response Content:

```
(
  ExecutionPayloadEnvelopes
)
```

Envelopes of blocks from the EIP-8142 fork onwards are served unsigned. The
requester MUST verify each such envelope against the bid of its beacon block, as
`verify_execution_payload_envelope` does, before relying on it.

The EIP-8142 fork-digest is introduced to the `context` enum to specify the
EIP-8142 envelope type.

<!-- eth_consensus_specs: skip -->

| `fork_version`         | Chunk SSZ type                         |
| ---------------------- | -------------------------------------- |
| `GLOAS_FORK_VERSION`   | `gloas.SignedExecutionPayloadEnvelope` |
| `EIP8142_FORK_VERSION` | `eip8142.ExecutionPayloadEnvelope`     |

#### ExecutionPayloadEnvelopesByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/execution_payload_envelopes_by_root/1/`

Response Content:

```
(
  ExecutionPayloadEnvelopes
)
```

Requests execution payload envelopes by `envelope.beacon_block_root`. Envelopes
of blocks from the EIP-8142 fork onwards are served unsigned. The requester MUST
verify each such envelope against the bid of its beacon block, as
`verify_execution_payload_envelope` does, before relying on it.

ExecutionPayloadEnvelopesByRoot remains the way to recover a payload whose
chunks were missed, for example after receiving a payload attestation or an
attestation with revealed status as true without having reconstructed the
payload.

The EIP-8142 fork-digest is introduced to the `context` enum to specify the
EIP-8142 envelope type.

<!-- eth_consensus_specs: skip -->

| `fork_version`         | Chunk SSZ type                         |
| ---------------------- | -------------------------------------- |
| `GLOAS_FORK_VERSION`   | `gloas.SignedExecutionPayloadEnvelope` |
| `EIP8142_FORK_VERSION` | `eip8142.ExecutionPayloadEnvelope`     |
