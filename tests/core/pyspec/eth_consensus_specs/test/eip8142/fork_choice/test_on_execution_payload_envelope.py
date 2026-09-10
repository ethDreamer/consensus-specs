from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8142_and_later,
)
from eth_consensus_specs.test.helpers.eip8142.chunks import (
    build_envelope_and_chunks,
    seed_chunks,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_execution_payload,
    check_head_against_root,
    setup_one_block_store,
)
from eth_consensus_specs.test.helpers.gossip import get_seen


@with_eip8142_and_later
@spec_state_test
def test_on_execution_payload_envelope_reconstructed_from_chunks(spec, state):
    """
    An envelope reconstructed from the fewest chunks that allow it, taken from
    the parity end, is accepted and moves the head's payload_status to FULL.
    """
    store, block_root, block_state, signed_block, test_steps = yield from setup_one_block_store(
        spec, state
    )
    check_head_against_root(spec, store, block_root)
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_EMPTY

    envelope, chunks = build_envelope_and_chunks(spec, block_state, block_root, signed_block)
    bid = signed_block.message.body.signed_execution_payload_bid.message
    data_chunk_count = spec.get_payload_data_chunk_count(bid.payload_length)

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(store, block_state.slot)
    seed_chunks(spec, seen, store, chunks[-data_chunk_count:], time_ms)
    reconstructed = spec.reconstruct_execution_payload_envelope(seen, store, block_root)
    assert reconstructed == envelope

    yield from add_execution_payload(spec, store, reconstructed, test_steps, valid=True)

    assert block_root in store.payloads
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_FULL

    yield "steps", test_steps


@with_eip8142_and_later
@spec_state_test
def test_on_execution_payload_envelope_wrong_payload_chunks_root(spec, state):
    """
    An envelope whose contents the bid does not commit to is rejected, even
    though every field the bid names matches.
    """
    store, block_root, block_state, signed_block, test_steps = yield from setup_one_block_store(
        spec, state
    )

    envelope = build_signed_execution_payload_envelope(spec, block_state, block_root, signed_block)
    envelope.payload.extra_data = spec.ExtraData(data=[0x42])
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps
