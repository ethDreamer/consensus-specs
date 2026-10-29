from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test_with_matching_config,
    with_eip8453_and_later,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import next_slots


def prepare_distinct_block_root(spec, state, slot):
    """
    Advance past ``slot`` and fabricate a distinct block root for it, so a vote
    for ``slot`` passes ``is_head_vote_same_slot``'s empty-slot guard.
    """
    next_slots(spec, state, slot + 1 - state.slot)
    root = spec.Root(b"\x02" * 32)
    state.block_roots[slot % spec.SLOTS_PER_HISTORICAL_ROOT] = root
    return root


def sign_head_vote_data(spec, state, data, validator_index):
    domain = spec.get_domain(state, spec.DOMAIN_HEAD_VOTE, spec.compute_epoch_at_slot(data.slot))
    signing_root = spec.compute_signing_root(data, domain)
    return spec.bls.Sign(privkeys[validator_index], signing_root)


def make_head_vote(spec, state, data, voter_indices):
    signatures = [sign_head_vote_data(spec, state, data, index) for index in voter_indices]
    return spec.HeadVote(
        voter_indices=spec.HeadVoteCommitteeIndices(data=voter_indices),
        data=data,
        signature=spec.bls.Aggregate(signatures),
    )


def make_support_bits(spec, vote, value=False):
    return spec.HeadVoteSupportBits(data=[spec.Boolean(value)] * len(vote.voter_indices))


def run_head_vote_processing(spec, state, head_vote, support_bits, valid=True):
    """
    Run ``process_head_vote``, yielding:
    - pre-state ('pre')
    - head_vote ('head_vote')
    - support bits ('head_vote_support')
    - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state
    yield "head_vote", head_vote
    yield "head_vote_support", support_bits

    if not valid:
        expect_assertion_error(lambda: spec.process_head_vote(state, head_vote, support_bits))
        yield "post", None
        return

    spec.process_head_vote(state, head_vote, support_bits)
    yield "post", state


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_head_vote_same_slot_pays_seats(spec, state):
    vote_slot = spec.Slot(2)
    root = prepare_distinct_block_root(spec, state, vote_slot)
    committee = spec.get_head_vote_committee(state, vote_slot)
    voter = committee[0]
    seats = sum(1 for index in committee if index == voter)
    data = spec.HeadVoteData(
        slot=vote_slot, beacon_block_root=root, payload_status=spec.PAYLOAD_STATUS_PENDING
    )
    assert spec.is_head_vote_same_slot(state, data)
    head_vote = make_head_vote(spec, state, data, [voter])
    support_bits = make_support_bits(spec, head_vote)
    balance_before = state.balances[voter]

    yield from run_head_vote_processing(spec, state, head_vote, support_bits)

    seat_reward = spec.get_head_vote_seat_reward(state)
    assert state.balances[voter] == balance_before + seats * seat_reward


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_head_vote_seats_paid_once(spec, state):
    vote_slot = spec.Slot(2)
    root = prepare_distinct_block_root(spec, state, vote_slot)
    committee = spec.get_head_vote_committee(state, vote_slot)
    voter = committee[0]
    data = spec.HeadVoteData(
        slot=vote_slot, beacon_block_root=root, payload_status=spec.PAYLOAD_STATUS_PENDING
    )
    head_vote = make_head_vote(spec, state, data, [voter])
    support_bits = make_support_bits(spec, head_vote)
    spec.process_head_vote(state, head_vote, support_bits)
    balance_after_first = state.balances[voter]

    # Re-processing records and pays nothing further
    yield from run_head_vote_processing(spec, state, head_vote, support_bits)

    assert state.balances[voter] == balance_after_first


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_head_vote_support_bit_for_older_slot_invalid(spec, state):
    vote_slot = spec.Slot(2)
    root = prepare_distinct_block_root(spec, state, vote_slot)
    # The vote is now two slots old; a set support bit requires the previous slot
    next_slots(spec, state, 1)
    committee = spec.get_head_vote_committee(state, vote_slot)
    data = spec.HeadVoteData(
        slot=vote_slot, beacon_block_root=root, payload_status=spec.PAYLOAD_STATUS_PENDING
    )
    head_vote = make_head_vote(spec, state, data, [committee[0]])
    support_bits = make_support_bits(spec, head_vote, value=True)

    yield from run_head_vote_processing(spec, state, head_vote, support_bits, valid=False)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_head_vote_non_member_invalid(spec, state):
    vote_slot = spec.Slot(2)
    root = prepare_distinct_block_root(spec, state, vote_slot)
    committee = spec.get_head_vote_committee(state, vote_slot)
    non_member = next(
        spec.ValidatorIndex(index)
        for index in range(len(state.validators))
        if index not in committee
    )
    data = spec.HeadVoteData(
        slot=vote_slot, beacon_block_root=root, payload_status=spec.PAYLOAD_STATUS_PENDING
    )
    head_vote = make_head_vote(spec, state, data, [non_member])
    support_bits = make_support_bits(spec, head_vote)

    yield from run_head_vote_processing(spec, state, head_vote, support_bits, valid=False)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_head_vote_same_slot_pending_status_required(spec, state):
    vote_slot = spec.Slot(2)
    root = prepare_distinct_block_root(spec, state, vote_slot)
    committee = spec.get_head_vote_committee(state, vote_slot)
    data = spec.HeadVoteData(
        slot=vote_slot, beacon_block_root=root, payload_status=spec.PAYLOAD_STATUS_FULL
    )
    assert spec.is_head_vote_same_slot(state, data)
    head_vote = make_head_vote(spec, state, data, [committee[0]])
    support_bits = make_support_bits(spec, head_vote)

    yield from run_head_vote_processing(spec, state, head_vote, support_bits, valid=False)
