from eth_consensus_specs.test.helpers.constants import (
    EIP8142,
)

EIP8142_FORK_TEST_META_TAGS = {
    "fork": EIP8142,
}


def run_fork_test(post_spec, pre_state):
    yield "pre", pre_state

    post_state = post_spec.upgrade_to_eip8142(pre_state.copy())

    # Stable fields
    stable_fields = [
        "genesis_time",
        "genesis_validators_root",
        "slot",
        "latest_block_header",
        "block_roots",
        "state_roots",
        "historical_roots",
        "eth1_data",
        "eth1_data_votes",
        "eth1_deposit_index",
        "validators",
        "balances",
        "randao_mixes",
        "slashings",
        "previous_epoch_participation",
        "current_epoch_participation",
        "justification_bits",
        "previous_justified_checkpoint",
        "current_justified_checkpoint",
        "finalized_checkpoint",
        "inactivity_scores",
        "current_sync_committee",
        "next_sync_committee",
        "latest_block_hash",
        "next_withdrawal_index",
        "next_withdrawal_validator_index",
        "historical_summaries",
        "deposit_requests_start_index",
        "deposit_balance_to_consume",
        "exit_balance_to_consume",
        "earliest_exit_epoch",
        "consolidation_balance_to_consume",
        "earliest_consolidation_epoch",
        "pending_deposits",
        "pending_partial_withdrawals",
        "pending_consolidations",
        "proposer_lookahead",
        "builders",
        "next_withdrawal_builder_index",
        "execution_payload_availability",
        "builder_pending_payments",
        "builder_pending_withdrawals",
        "payload_expected_withdrawals",
        "ptc_window",
    ]
    for field in stable_fields:
        assert getattr(pre_state, field) == getattr(post_state, field)

    # Modified fields
    modified_fields = ["fork", "latest_execution_payload_bid"]
    for field in modified_fields:
        assert getattr(pre_state, field) != getattr(post_state, field)

    # The bid keeps every field it had and gains an empty chunk commitment
    pre_bid = pre_state.latest_execution_payload_bid
    post_bid = post_state.latest_execution_payload_bid
    for field in type(pre_bid).__annotations__:
        assert getattr(pre_bid, field) == getattr(post_bid, field)
    assert post_bid.payload_chunks_root == post_spec.Root()
    assert post_bid.payload_length == 0

    assert pre_state.fork.current_version == post_state.fork.previous_version
    assert post_state.fork.current_version == post_spec.config.EIP8142_FORK_VERSION
    assert post_state.fork.epoch == post_spec.get_current_epoch(post_state)

    yield "post", post_state

    return post_state
