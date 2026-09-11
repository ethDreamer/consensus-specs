from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
    get_execution_payload_chunks,
    get_execution_payload_contents,
)


def build_envelope_and_chunks(spec, state, block_root, signed_block, execution_requests=None):
    """
    Build the envelope honoring the bid of ``signed_block`` from its
    post-state ``state``, and the chunks its builder broadcasts for it.
    """
    envelope = build_signed_execution_payload_envelope(
        spec, state, block_root, signed_block, execution_requests=execution_requests
    )
    chunks = get_execution_payload_chunks(
        spec, signed_block.message, envelope.payload, envelope.execution_requests
    )
    return envelope, chunks


def build_inconsistent_chunks(spec, block, payload, execution_requests=None):
    """
    Build chunks whose last parity chunk is garbage, together with the root a
    dishonest builder would commit to for them. Every chunk carries a valid
    proof against that root, yet no subset recovers a payload that the root
    commits to.
    """
    contents = get_execution_payload_contents(spec, payload, execution_requests)
    chunks = list(spec.compute_payload_chunks(spec.ssz_serialize(contents)))
    chunks[-1] = spec.PayloadChunkData(data=b"\x42" * len(chunks[-1]))
    chunk_hashes = spec.PayloadChunkHashes(data=[spec.sha256(bytes(chunk)) for chunk in chunks])
    root = spec.hash_tree_root(chunk_hashes)
    block_root = spec.hash_tree_root(block)
    execution_payload_chunks = [
        spec.ExecutionPayloadChunk(
            beacon_block_root=block_root,
            slot=block.slot,
            index=spec.PayloadChunkIndex(index),
            data=chunk,
            proof=spec.PayloadChunkProof(
                data=spec.compute_merkle_proof(
                    chunk_hashes, spec.get_generalized_index(spec.PayloadChunkHashes, index)
                )
            ),
        )
        for index, chunk in enumerate(chunks)
    ]
    return execution_payload_chunks, root


def seed_chunks(spec, seen, store, chunks, current_time_ms):
    """
    Validate ``chunks`` for gossip in order, asserting each is accepted.
    """
    for chunk in chunks:
        spec.validate_execution_payload_chunk_gossip(
            seen=seen, store=store, chunk=chunk, current_time_ms=current_time_ms
        )
