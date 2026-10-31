from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test_with_matching_config,
    with_eip8453_and_later,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import next_slots


def sign_safe_vote_data(spec, state, data, validator_index):
    epoch = spec.compute_epoch_at_slot(spec.compute_start_slot_at_round(data.round))
    domain = spec.get_domain(state, spec.DOMAIN_SAFE_VOTE, epoch)
    signing_root = spec.compute_signing_root(data, domain)
    return spec.bls.Sign(privkeys[validator_index], signing_root)


def make_safe_vote(spec, state, data, voter_indices, signing_indices=None):
    """
    Build a ``SafeVote`` aggregate over ``data`` for ``voter_indices``. The
    signatures come from ``signing_indices`` when given, to build invalid votes.
    """
    if signing_indices is None:
        signing_indices = voter_indices
    signatures = [sign_safe_vote_data(spec, state, data, index) for index in signing_indices]
    return spec.SafeVote(
        voter_indices=spec.SafeVoteIndices(data=voter_indices),
        data=data,
        signature=spec.bls.Aggregate(signatures),
    )


def default_safe_vote_data(spec, state, round=None, root=b"\x01" * 32):
    if round is None:
        round = spec.get_current_round(state)
    return spec.SafeVoteData(
        round=round,
        beacon_block_root=root,
        payload_status=spec.PAYLOAD_STATUS_PENDING,
    )


def run_safe_vote_processing(spec, state, safe_vote, valid=True):
    """
    Run ``process_safe_vote``, yielding:
    - pre-state ('pre')
    - safe_vote ('safe_vote')
    - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state
    yield "safe_vote", safe_vote

    if not valid:
        expect_assertion_error(lambda: spec.process_safe_vote(state, safe_vote))
        yield "post", None
        return

    spec.process_safe_vote(state, safe_vote)
    yield "post", state


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_valid(spec, state):
    voters = [spec.ValidatorIndex(i) for i in range(8)]
    data = default_safe_vote_data(spec, state)
    safe_vote = make_safe_vote(spec, state, data, voters)
    proposer_index = spec.get_beacon_proposer_index(state)
    proposer_balance = state.balances[proposer_index]

    yield from run_safe_vote_processing(spec, state, safe_vote)

    for index in voters:
        assert spec.has_flag(state.round_participation[index], spec.SAFE_VOTE_FLAG_INDEX)
    assert state.balances[proposer_index] > proposer_balance


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_credited_once(spec, state):
    voters = [spec.ValidatorIndex(i) for i in range(4)]
    data = default_safe_vote_data(spec, state)
    safe_vote = make_safe_vote(spec, state, data, voters)
    spec.process_safe_vote(state, safe_vote)
    proposer_index = spec.get_beacon_proposer_index(state)
    proposer_balance = state.balances[proposer_index]

    # Re-processing the same vote is valid but credits and pays nothing
    yield from run_safe_vote_processing(spec, state, safe_vote)

    assert state.balances[proposer_index] == proposer_balance


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_second_distinct_data_valid(spec, state):
    voters = [spec.ValidatorIndex(0)]
    first = default_safe_vote_data(spec, state, root=b"\x01" * 32)
    second = default_safe_vote_data(spec, state, root=b"\x02" * 32)
    spec.process_safe_vote(state, make_safe_vote(spec, state, first, voters))
    proposer_index = spec.get_beacon_proposer_index(state)
    proposer_balance = state.balances[proposer_index]

    # Equivocation evidence is includable; the flag was already credited
    yield from run_safe_vote_processing(spec, state, make_safe_vote(spec, state, second, voters))

    assert state.balances[proposer_index] == proposer_balance


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_previous_round_no_credit(spec, state):
    data = default_safe_vote_data(spec, state)
    voters = [spec.ValidatorIndex(i) for i in range(4)]
    safe_vote = make_safe_vote(spec, state, data, voters)
    next_slots(spec, state, spec.SLOTS_PER_ROUND)
    assert spec.get_current_round(state) == data.round + 1

    yield from run_safe_vote_processing(spec, state, safe_vote)

    for index in voters:
        assert not spec.has_flag(state.round_participation[index], spec.SAFE_VOTE_FLAG_INDEX)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_expired_round_invalid(spec, state):
    data = default_safe_vote_data(spec, state)
    voters = [spec.ValidatorIndex(0)]
    safe_vote = make_safe_vote(spec, state, data, voters)
    next_slots(spec, state, spec.SLOTS_PER_ROUND * (int(spec.SAFE_VOTE_EXPIRY_ROUNDS) + 1))

    yield from run_safe_vote_processing(spec, state, safe_vote, valid=False)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_future_round_invalid(spec, state):
    data = default_safe_vote_data(spec, state, round=spec.get_current_round(state) + 1)
    safe_vote = make_safe_vote(spec, state, data, [spec.ValidatorIndex(0)])

    yield from run_safe_vote_processing(spec, state, safe_vote, valid=False)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_unsorted_voters_invalid(spec, state):
    data = default_safe_vote_data(spec, state)
    safe_vote = make_safe_vote(spec, state, data, [spec.ValidatorIndex(2), spec.ValidatorIndex(1)])

    yield from run_safe_vote_processing(spec, state, safe_vote, valid=False)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_duplicate_voter_invalid(spec, state):
    data = default_safe_vote_data(spec, state)
    safe_vote = make_safe_vote(spec, state, data, [spec.ValidatorIndex(1), spec.ValidatorIndex(1)])

    yield from run_safe_vote_processing(spec, state, safe_vote, valid=False)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_empty_voters_invalid(spec, state):
    data = default_safe_vote_data(spec, state)
    safe_vote = spec.SafeVote(
        voter_indices=spec.SafeVoteIndices(),
        data=data,
        signature=spec.bls.G2_POINT_AT_INFINITY,
    )

    yield from run_safe_vote_processing(spec, state, safe_vote, valid=False)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_invalid_payload_status_invalid(spec, state):
    data = default_safe_vote_data(spec, state)
    data.payload_status = spec.PayloadStatus(3)
    safe_vote = make_safe_vote(spec, state, data, [spec.ValidatorIndex(0)])

    yield from run_safe_vote_processing(spec, state, safe_vote, valid=False)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_wrong_signer_invalid(spec, state):
    data = default_safe_vote_data(spec, state)
    safe_vote = make_safe_vote(
        spec, state, data, [spec.ValidatorIndex(0)], signing_indices=[spec.ValidatorIndex(1)]
    )

    yield from run_safe_vote_processing(spec, state, safe_vote, valid=False)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_safe_vote_inactive_voter_invalid(spec, state):
    voter = spec.ValidatorIndex(0)
    state.validators[voter].exit_epoch = spec.get_current_epoch(state)
    data = default_safe_vote_data(spec, state)
    safe_vote = make_safe_vote(spec, state, data, [voter])

    yield from run_safe_vote_processing(spec, state, safe_vote, valid=False)
