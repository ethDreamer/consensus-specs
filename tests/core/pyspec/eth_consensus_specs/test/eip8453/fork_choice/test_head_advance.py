from eth_consensus_specs.test.context import (
    spec_state_test_with_matching_config,
    with_eip8453_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


def sign_head_vote_data(spec, state, data, validator_index):
    domain = spec.get_domain(state, spec.DOMAIN_HEAD_VOTE, spec.compute_epoch_at_slot(data.slot))
    signing_root = spec.compute_signing_root(data, domain)
    return spec.bls.Sign(privkeys[validator_index], signing_root)


def apply_block_at_next_slot(spec, state, store):
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    time_ms = spec.compute_time_at_slot_ms(store.genesis_time_ms, block.slot)
    spec.on_tick(store, time_ms)
    spec.on_block(store, signed_block)
    return block.hash_tree_root(), block.slot


def make_head_vote_data(spec, store, head, vote_slot):
    # The validator guide's rule: a same-slot head is named pending,
    # an older head keeps the payload status the walk selected
    if store.blocks[head.root].slot == vote_slot:
        payload_status = spec.PAYLOAD_STATUS_PENDING
    else:
        payload_status = head.payload_status
    return spec.HeadVoteData(
        slot=vote_slot,
        beacon_block_root=head.root,
        payload_status=payload_status,
    )


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_vote_head_reaches_fresh_proposal(spec, state):
    # A proposal must be reachable by the vote walk in its own slot: the
    # previous slot's payload decision is always eligible, so the walk can
    # cross the parent's payload node without any vote weight.
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)
    block_root, block_slot = apply_block_at_next_slot(spec, state, store)

    vote_time_ms = (
        spec.compute_time_at_slot_ms(store.genesis_time_ms, block_slot)
        + spec.get_head_vote_due_ms()
    )
    spec.on_tick(store, vote_time_ms)

    head = spec.get_ac_vote_head(store)
    assert head.root == block_root


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_honest_votes_advance_proposal_head(spec, state):
    # The committee honestly votes the head the vote walk names; the next
    # slot's proposer must then build on that block, not on the anchor.
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)
    block_root, block_slot = apply_block_at_next_slot(spec, state, store)

    vote_time_ms = (
        spec.compute_time_at_slot_ms(store.genesis_time_ms, block_slot)
        + spec.get_head_vote_due_ms()
    )
    spec.on_tick(store, vote_time_ms)

    head = spec.get_ac_vote_head(store)
    assert head.root == block_root

    head_state = store.block_states[block_root]
    committee = spec.get_head_vote_committee(head_state, block_slot)
    data = make_head_vote_data(spec, store, head, block_slot)
    for validator_index in sorted(set(committee)):
        message = spec.HeadVoteMessage(
            validator_index=validator_index,
            data=data,
            signature=sign_head_vote_data(spec, head_state, data, validator_index),
        )
        spec.on_head_vote_message(store, message)

    next_slot_ms = spec.compute_time_at_slot_ms(store.genesis_time_ms, block_slot + 1)
    spec.on_tick(store, next_slot_ms)

    proposal_head, _, _ = spec.get_ac_proposal(store)
    assert proposal_head.root == block_root
    assert proposal_head.payload_status != spec.PAYLOAD_STATUS_PENDING
