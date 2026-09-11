# EIP-8142 -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Builder activities](#builder-activities)
  - [Constructing the `SignedExecutionPayloadBid`](#constructing-the-signedexecutionpayloadbid)
  - [Constructing the `ExecutionPayloadChunk`s](#constructing-the-executionpayloadchunks)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
builder" to implement EIP-8142.

## Builder activities

### Constructing the `SignedExecutionPayloadBid`

The bid additionally commits to the chunks of the payload it will reveal. Let
`contents` be
`ExecutionPayloadContents(payload=payload, execution_requests=execution_requests)`,
where `payload` and `execution_requests` are those returned by
`engine_getPayloadV6` when constructing the bid, and let
`payload_bytes = ssz_serialize(contents)`.

14. Set `bid.payload_chunks_root` to
    `compute_payload_chunks_root(compute_payload_chunks(payload_bytes))`.
15. Set `bid.payload_length` to `len(payload_bytes)`. The builder **MUST**
    construct a payload for which
    `get_payload_chunk_size(bid.payload_length) <= MAX_PAYLOAD_CHUNK_SIZE`.

### Constructing the `ExecutionPayloadChunk`s

When the proposer publishes a valid `SignedBeaconBlock` containing a signed
commitment by the builder, the builder is expected to broadcast the chunks of
the committed payload instead of a `SignedExecutionPayloadEnvelope`, which no
longer exists. We alias `block` to be the corresponding `BeaconBlock` and
`contents` to be the `ExecutionPayloadContents` the bid commits to.

The builder constructs the chunks using:

```python
def get_execution_payload_chunks(
    block: BeaconBlock, contents: ExecutionPayloadContents
) -> Sequence[ExecutionPayloadChunk]:
    chunks = compute_payload_chunks(ssz_serialize(contents))
    chunk_hashes = PayloadChunkHashes(data=[sha256(bytes(chunk)) for chunk in chunks])
    return [
        ExecutionPayloadChunk(
            beacon_block_root=hash_tree_root(block),
            slot=block.slot,
            index=PayloadChunkIndex(index),
            data=chunk,
            proof=PayloadChunkProof(
                data=compute_merkle_proof(
                    chunk_hashes, get_generalized_index(PayloadChunkHashes, index)
                )
            ),
        )
        for index, chunk in enumerate(chunks)
    ]
```

Then the builder broadcasts every chunk on the `execution_payload_chunk` global
gossip topic. The builder SHOULD broadcast the chunks in index order, so that
nodes receiving all data chunks can reconstruct the payload without decoding.

The rules for honestly withheld payloads are unchanged: a builder that withholds
its payload broadcasts no chunks.
