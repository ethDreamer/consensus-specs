# EIP-8142 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `verify_execution_payload_envelope`](#modified-verify_execution_payload_envelope)
- [Handlers](#handlers)
  - [Modified `on_execution_payload_envelope`](#modified-on_execution_payload_envelope)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork-choice accompanying EIP-8142.

The execution payload envelope reaches fork choice unsigned, either
reconstructed from gossiped chunks or retrieved by request. In both cases it is
authenticated against the chunk commitment in the bid of its beacon block.

## Helpers

### Modified `verify_execution_payload_envelope`

*Note*: The signature check is replaced by the chunk commitment check. Nodes
that reconstructed `envelope` from chunks have already performed that check
during reconstruction and MAY skip it here.

```python
def verify_execution_payload_envelope(
    state: BeaconState,
    # [Modified in EIP8142]
    envelope: ExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
) -> None:
    payload = envelope.payload

    # Verify consistency with the beacon block
    header = state.latest_block_header.copy()
    header.state_root = hash_tree_root(state)
    assert envelope.beacon_block_root == hash_tree_root(header)
    assert envelope.parent_beacon_block_root == state.latest_block_header.parent_root

    # Verify consistency with the committed bid
    bid = state.latest_execution_payload_bid
    assert envelope.builder_index == bid.builder_index
    assert payload.prev_randao == bid.prev_randao
    assert payload.gas_limit == bid.gas_limit
    assert payload.block_hash == bid.block_hash
    assert hash_tree_root(envelope.execution_requests) == bid.execution_requests_root
    # [New in EIP8142]
    payload_bytes = ssz_serialize(get_execution_payload_contents(envelope))
    assert is_valid_payload_chunks_root(bid, payload_bytes)

    # Verify the execution payload is valid
    assert payload.slot_number == state.slot
    assert payload.parent_hash == state.latest_block_hash
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    assert hash_tree_root(payload.withdrawals) == hash_tree_root(state.payload_expected_withdrawals)

    # Compute versioned hashes
    versioned_hashes = VersionedHashes()
    for commitment in bid.blob_kzg_commitments:
        versioned_hashes.append(kzg_commitment_to_versioned_hash(commitment))

    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=envelope.parent_beacon_block_root,
            execution_requests=envelope.execution_requests,
        )
    )
```

## Handlers

### Modified `on_execution_payload_envelope`

The handler `on_execution_payload_envelope` is called when the node has an
`ExecutionPayloadEnvelope` to sync, whether reconstructed from chunks received
on the `execution_payload_chunk` gossip topic or retrieved through the Req/Resp
domain.

```python
def on_execution_payload_envelope(
    store: Store,
    # [Modified in EIP8142]
    envelope: ExecutionPayloadEnvelope,
) -> None:
    """
    Run ``on_execution_payload_envelope`` upon receiving a new execution payload envelope.
    """
    # The corresponding beacon block root needs to be known
    assert envelope.beacon_block_root in store.block_states

    # Check if blob data is available
    # If not, this payload MAY be queued and subsequently considered when blob data becomes available
    assert is_data_available(envelope.beacon_block_root)

    state = store.block_states[envelope.beacon_block_root]

    # Verify the execution payload envelope
    verify_execution_payload_envelope(state, envelope, EXECUTION_ENGINE)

    # Check if this payload satisfies the inclusion list constraints
    # If not, add this payload to the store as inclusion list constraints unsatisfied
    record_payload_inclusion_list_satisfaction(
        store, envelope.beacon_block_root, envelope.payload, EXECUTION_ENGINE
    )

    # Add execution payload envelope to the store
    store.payloads[envelope.beacon_block_root] = envelope
```
