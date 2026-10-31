from eth_consensus_specs.test.context import (
    spec_state_test_with_matching_config,
    with_eip8453_and_later,
)


def set_full_participation(spec, state, field):
    setattr(
        state,
        field,
        spec.HeightParticipation(data=[spec.Boolean(1)] * len(state.validators)),
    )


def run_height_events(spec, state):
    """
    Run ``process_height_events``, yielding:
    - pre-state ('pre')
    - post-state ('post').
    """
    yield "pre", state
    spec.process_height_events(state)
    yield "post", state


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_target_quorum_justifies_and_advances(spec, state):
    height = state.target_checkpoint.height
    set_full_participation(spec, state, "target_participation")

    yield from run_height_events(spec, state)

    assert state.justified_checkpoint.height == height
    assert state.target_checkpoint.height == height + 1
    assert len(state.pending_finality) == 1


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_nonjustifiable_height_advances_without_justifying(spec, state):
    # Enter the next nonjustifiable height under finality debt
    state.target_checkpoint.height = spec.Height(spec.NONJUSTIFIABLE_HEIGHT_PERIOD - 1)
    spec.advance_height(state)
    assert state.nonjustifiable
    justified_height = state.justified_checkpoint.height
    height = state.target_checkpoint.height
    set_full_participation(spec, state, "target_participation")

    yield from run_height_events(spec, state)

    assert state.justified_checkpoint.height == justified_height
    assert len(state.pending_finality) == 0
    assert state.target_checkpoint.height == height + 1
    assert not state.nonjustifiable


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_kth_height_without_debt_justifies(spec, state):
    # The K-th height is justifiable when there is no finality debt
    state.target_checkpoint.height = spec.Height(spec.NONJUSTIFIABLE_HEIGHT_PERIOD - 1)
    state.finalized_checkpoint.height = spec.Height(
        spec.NONJUSTIFIABLE_HEIGHT_PERIOD - spec.FINALITY_DEBT_THRESHOLD
    )
    spec.advance_height(state)
    assert not state.nonjustifiable
    height = state.target_checkpoint.height
    set_full_participation(spec, state, "target_participation")

    yield from run_height_events(spec, state)

    assert state.justified_checkpoint.height == height


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_timeout_quorum_waits_for_the_delay(spec, state):
    height = state.target_checkpoint.height
    set_full_participation(spec, state, "progress_participation")
    assert state.slot < state.target_slot + spec.TIMEOUT_DELAY_SLOTS

    yield from run_height_events(spec, state)

    assert state.target_checkpoint.height == height
    assert state.justified_checkpoint.height < height


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_timeout_quorum_advances_after_the_delay(spec, state):
    height = state.target_checkpoint.height
    set_full_participation(spec, state, "progress_participation")
    state.slot = state.target_slot + spec.TIMEOUT_DELAY_SLOTS

    yield from run_height_events(spec, state)

    assert state.target_checkpoint.height == height + 1
    assert state.justified_checkpoint.height < height
