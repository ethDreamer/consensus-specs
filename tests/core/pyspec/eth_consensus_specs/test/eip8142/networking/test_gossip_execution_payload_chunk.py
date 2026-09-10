import random

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8142_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.eip8142.chunks import (
    build_envelope_and_chunks,
    build_inconsistent_chunks,
    seed_chunks,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_execution_payload_for_bid,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    setup_store_with_failed_block,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

TOPIC = "execution_payload_chunk"


def setup_store_with_block(spec, state):
    """Apply one block to the genesis store. Returns store, blocks, signed block, block root."""
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    return store, [signed_anchor, signed_block], signed_block, block_root


def setup_chunk_test(spec, state):
    """
    Set up a store with one block and the chunks of its payload, yielding the
    fixture files. Returns the store, block root, envelope, chunks, seen set,
    the current time, and the messages list to append to.
    """
    anchor_state = state.copy()
    yield "topic", "meta", TOPIC

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    envelope, chunks = build_envelope_and_chunks(spec, state, block_root, signed_block)
    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    return store, block_root, envelope, chunks, seen, time_ms, []


def run_chunk(spec, seen, store, chunk, time_ms, messages, expected, reason=None):
    result, actual_reason = run_validate_gossip(
        spec, seen=seen, store=store, chunk=chunk, current_time_ms=time_ms
    )
    assert result == expected, (result, actual_reason)
    assert actual_reason == reason
    entry = {
        "current_time_ms": int(time_ms),
        "message": get_filename(chunk),
        "expected": result,
    }
    if reason is not None:
        entry["reason"] = reason
    messages.append(entry)


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__valid(spec, state):
    """Every chunk of a known block's payload, data or parity, passes gossip validation."""
    store, block_root, _envelope, chunks, seen, time_ms, messages = yield from setup_chunk_test(
        spec, state
    )
    bid = store.blocks[block_root].body.signed_execution_payload_bid.message
    assert len(chunks) == spec.get_payload_chunk_count(bid.payload_length)

    for chunk in chunks:
        yield get_filename(chunk), chunk
        time_ms += 10
        run_chunk(spec, seen, store, chunk, time_ms, messages, "valid")

    assert set(seen.execution_payload_chunks[block_root]) == {chunk.index for chunk in chunks}

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__ignore_duplicate(spec, state):
    """The second chunk with the same block root and index is ignored."""
    store, _block_root, _envelope, chunks, seen, time_ms, messages = yield from setup_chunk_test(
        spec, state
    )
    chunk = chunks[0]
    yield get_filename(chunk), chunk

    time_ms += 10
    run_chunk(spec, seen, store, chunk, time_ms, messages, "valid")
    time_ms += 10
    run_chunk(
        spec,
        seen,
        store,
        chunk,
        time_ms,
        messages,
        "ignore",
        "already seen chunk for this block root and index",
    )

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__ignore_future_slot(spec, state):
    """A chunk from a slot the node has not reached yet is ignored."""
    store, _block_root, _envelope, chunks, seen, time_ms, messages = yield from setup_chunk_test(
        spec, state
    )
    chunk = chunks[0]
    yield get_filename(chunk), chunk

    # One slot before the block's slot, beyond the clock disparity
    time_ms = spec.compute_time_at_slot_ms(store, chunk.slot - 1)
    run_chunk(spec, seen, store, chunk, time_ms, messages, "ignore", "chunk is from a future slot")

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__ignore_block_unseen(spec, state):
    """A chunk for an unknown beacon block is ignored."""
    store, _block_root, _envelope, chunks, seen, time_ms, messages = yield from setup_chunk_test(
        spec, state
    )
    chunk = chunks[0].copy()
    chunk.beacon_block_root = spec.Root(b"\xab" * 32)
    yield get_filename(chunk), chunk

    time_ms += 10
    run_chunk(
        spec, seen, store, chunk, time_ms, messages, "ignore", "chunk's block has not been seen"
    )

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__reject_block_failed(spec, state):
    """A chunk for a block that failed validation is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", TOPIC

    store, signed_anchor, signed_failed_block = setup_store_with_failed_block(spec, state)
    blocks = [signed_anchor, signed_failed_block]
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_failed_block), "failed": True},
        ],
    )

    failed_root = signed_failed_block.message.hash_tree_root()
    _, chunks = build_envelope_and_chunks(spec, state, failed_root, signed_failed_block)
    chunk = chunks[0]
    yield get_filename(chunk), chunk

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 10
    run_chunk(
        spec, seen, store, chunk, time_ms, messages, "reject", "chunk's block failed validation"
    )

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__ignore_pre_finalized(spec, state):
    """A chunk from a slot before the latest finalized slot is ignored."""
    store, block_root, _envelope, chunks, seen, time_ms, messages = yield from setup_chunk_test(
        spec, state
    )
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.compute_epoch_at_slot(state.slot) + 1, root=block_root
    )
    yield (
        "finalized_checkpoint",
        "meta",
        {
            "epoch": int(store.finalized_checkpoint.epoch),
            "root": "0x" + store.finalized_checkpoint.root.hex(),
        },
    )
    chunk = chunks[0]
    yield get_filename(chunk), chunk

    time_ms += 10
    run_chunk(
        spec,
        seen,
        store,
        chunk,
        time_ms,
        messages,
        "ignore",
        "chunk is from a slot before the latest finalized slot",
    )

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__ignore_payload_verified(spec, state):
    """A chunk for a block whose payload is already verified is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", TOPIC

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    envelope, chunks = build_envelope_and_chunks(spec, state, block_root, signed_block)
    # The payload arrived whole, or was reconstructed already
    store.payloads[block_root] = envelope

    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield get_filename(envelope), envelope
    blocks_meta = [{"block": get_filename(b)} for b in blocks]
    blocks_meta[-1]["payload"] = get_filename(envelope)
    yield "blocks", "meta", blocks_meta

    chunk = chunks[0]
    yield get_filename(chunk), chunk

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 10
    run_chunk(
        spec,
        seen,
        store,
        chunk,
        time_ms,
        messages,
        "ignore",
        "payload for chunk's block is already verified",
    )

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__reject_slot_mismatch(spec, state):
    """A chunk whose slot differs from its block's slot is rejected."""
    store, _block_root, _envelope, chunks, seen, time_ms, messages = yield from setup_chunk_test(
        spec, state
    )
    chunk = chunks[0].copy()
    chunk.slot = spec.Slot(chunk.slot - 1)
    yield get_filename(chunk), chunk

    time_ms += 10
    run_chunk(
        spec,
        seen,
        store,
        chunk,
        time_ms,
        messages,
        "reject",
        "chunk's slot does not match block's slot",
    )

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__reject_index_out_of_range(spec, state):
    """A chunk with an index beyond the chunk count the bid commits to is rejected."""
    store, _block_root, _envelope, chunks, seen, time_ms, messages = yield from setup_chunk_test(
        spec, state
    )
    chunk = chunks[0].copy()
    chunk.index = spec.PayloadChunkIndex(len(chunks))
    yield get_filename(chunk), chunk

    time_ms += 10
    run_chunk(
        spec, seen, store, chunk, time_ms, messages, "reject", "chunk's index is out of range"
    )

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__reject_corrupted_data(spec, state):
    """A chunk whose data does not match its proof is rejected."""
    store, _block_root, _envelope, chunks, seen, time_ms, messages = yield from setup_chunk_test(
        spec, state
    )
    chunk = chunks[-1].copy()
    data = bytearray(chunk.data)
    data[0] ^= 0x01
    chunk.data = spec.PayloadChunkData(bytes(data))
    yield get_filename(chunk), chunk

    time_ms += 10
    run_chunk(spec, seen, store, chunk, time_ms, messages, "reject", "invalid chunk proof")

    yield "messages", "meta", messages


@with_eip8142_and_later
@with_presets([MINIMAL], reason="the test payload must span more than one data chunk")
@spec_state_test
def test_gossip_execution_payload_chunk__reject_wrong_index(spec, state):
    """A valid chunk relabeled with another in-range index is rejected."""
    store, _block_root, _envelope, chunks, seen, time_ms, messages = yield from setup_chunk_test(
        spec, state
    )
    chunk = chunks[0].copy()
    chunk.index = spec.PayloadChunkIndex(1)
    yield get_filename(chunk), chunk

    time_ms += 10
    run_chunk(spec, seen, store, chunk, time_ms, messages, "reject", "invalid chunk proof")

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_gossip_execution_payload_chunk__reject_wrong_block(spec, state):
    """A chunk of one block's payload presented for another known block is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", TOPIC

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    _, chunks = build_envelope_and_chunks(spec, state, block_root, signed_block)

    # A second block with a different bid, and hence a different chunks root
    other_block = build_empty_block_for_next_slot(spec, state)
    signed_other = state_transition_and_sign_block(spec, state, other_block)
    other_root = signed_other.message.hash_tree_root()
    store.blocks[other_root] = signed_other.message
    store.block_states[other_root] = state.copy()
    blocks.append(signed_other)

    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    chunk = chunks[0].copy()
    chunk.beacon_block_root = other_root
    chunk.slot = signed_other.message.slot
    yield get_filename(chunk), chunk

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 10
    run_chunk(spec, seen, store, chunk, time_ms, messages, "reject", "invalid chunk proof")

    yield "messages", "meta", messages


#
# Reconstruction
#


@with_eip8142_and_later
@with_presets([MINIMAL], reason="the test payload must span more than one data chunk")
@spec_state_test
def test_reconstruct_execution_payload_envelope__from_any_subset(spec, state):
    """Any subset of chunks as large as the data recovers the builder's envelope."""
    store, block_root, envelope, chunks, seen, time_ms, messages = yield from setup_chunk_test(
        spec, state
    )
    bid = store.blocks[block_root].body.signed_execution_payload_bid.message
    data_chunk_count = spec.get_payload_data_chunk_count(bid.payload_length)
    assert 1 < data_chunk_count < len(chunks)

    rng = random.Random(8142)
    subsets = [
        chunks[:data_chunk_count],
        chunks[data_chunk_count:],
        rng.sample(chunks, data_chunk_count),
    ]
    for subset in subsets:
        seen = get_seen(spec)
        seed_chunks(spec, seen, store, subset, time_ms)
        reconstructed = spec.reconstruct_execution_payload_envelope(seen, store, block_root)
        assert reconstructed == envelope
        assert seen.execution_payloads[envelope.payload.block_hash] == envelope.payload

    yield "messages", "meta", messages


@with_eip8142_and_later
@spec_state_test
def test_reconstruct_execution_payload_envelope__inconsistent_codeword(spec, state):
    """
    Chunks that are not a codeword pass gossip validation one by one, yet
    reconstruction fails whichever subset is used.
    """
    anchor_state = state.copy()
    yield "topic", "meta", TOPIC

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    # Work out the payload the bid would honestly commit to, then commit to a
    # corrupted extension of it instead
    block = build_empty_block_for_next_slot(spec, state)
    trial_state = state.copy()
    state_transition_and_sign_block(spec, trial_state, block.copy())
    payload = build_execution_payload_for_bid(spec, trial_state)
    bid = block.body.signed_execution_payload_bid.message
    _, bid.payload_chunks_root = build_inconsistent_chunks(spec, block, payload)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    chunks, _ = build_inconsistent_chunks(spec, signed_block.message, payload)

    yield "state", anchor_state
    for signed in [signed_anchor, signed_block]:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in [signed_anchor, signed_block]]

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    for chunk in chunks:
        yield get_filename(chunk), chunk
        time_ms += 10
        run_chunk(spec, seen, store, chunk, time_ms, messages, "valid")

    data_chunk_count = spec.get_payload_data_chunk_count(bid.payload_length)
    subsets = [chunks[:data_chunk_count], chunks[-data_chunk_count:]]
    for subset in subsets:
        seen = get_seen(spec)
        seed_chunks(spec, seen, store, subset, time_ms)
        try:
            spec.reconstruct_execution_payload_envelope(seen, store, block_root)
            raise Exception("reconstruction should fail")
        except AssertionError:
            pass

    yield "messages", "meta", messages
