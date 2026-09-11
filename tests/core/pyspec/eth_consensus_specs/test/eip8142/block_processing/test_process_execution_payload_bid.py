from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8142_and_later,
)
from eth_consensus_specs.test.gloas.block_processing.test_process_execution_payload_bid import (
    prepare_block_with_execution_payload_bid,
)
from eth_consensus_specs.test.helpers.execution_payload_bid import (
    run_execution_payload_bid_processing,
)


@with_eip8142_and_later
@spec_state_test
def test_process_execution_payload_bid_valid_max_payload_length(spec, state):
    """
    A bid committing to the largest payload whose chunks fit in
    ``MAX_PAYLOAD_CHUNK_SIZE`` is valid.
    """
    block, signed_bid = prepare_block_with_execution_payload_bid(spec, state)
    signed_bid.message.payload_length = spec.MAX_PAYLOAD_DATA_CHUNKS * spec.MAX_PAYLOAD_CHUNK_SIZE
    assert (
        spec.get_payload_chunk_size(signed_bid.message.payload_length)
        == spec.MAX_PAYLOAD_CHUNK_SIZE
    )

    yield from run_execution_payload_bid_processing(spec, state, block)


@with_eip8142_and_later
@spec_state_test
def test_process_execution_payload_bid_invalid_zero_payload_length(spec, state):
    """
    A bid committing to an empty payload is invalid.
    """
    block, signed_bid = prepare_block_with_execution_payload_bid(spec, state)
    signed_bid.message.payload_length = spec.Uint64(0)

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)


@with_eip8142_and_later
@spec_state_test
def test_process_execution_payload_bid_invalid_payload_length_too_large(spec, state):
    """
    A bid committing to a payload whose chunks would exceed
    ``MAX_PAYLOAD_CHUNK_SIZE`` is invalid.
    """
    block, signed_bid = prepare_block_with_execution_payload_bid(spec, state)
    signed_bid.message.payload_length = (
        spec.MAX_PAYLOAD_DATA_CHUNKS * spec.MAX_PAYLOAD_CHUNK_SIZE + 1
    )
    assert (
        spec.get_payload_chunk_size(signed_bid.message.payload_length) > spec.MAX_PAYLOAD_CHUNK_SIZE
    )

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)
