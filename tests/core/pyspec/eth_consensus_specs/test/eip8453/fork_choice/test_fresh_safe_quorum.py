from eth_consensus_specs.test.context import (
    spec_state_test_with_matching_config,
    with_eip8453_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.state import (
    next_slot,
    state_transition_and_sign_block,
)


def apply_empty_blocks(spec, state, store, count):
    """
    Build and apply ``count`` empty blocks on ``state``'s chain, ticking the
    store to each block's slot. Returns the applied block roots in order.
    """
    roots = []
    for _ in range(count):
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        time_ms = spec.compute_time_at_slot_ms(store.genesis_time_ms, block.slot)
        spec.on_tick(store, time_ms)
        spec.on_block(store, signed_block)
        roots.append(block.hash_tree_root())
    return roots


def pending_node(spec, root):
    return spec.ForkChoiceNode(root=root, payload_status=spec.PAYLOAD_STATUS_PENDING)


def set_justified(spec, store, root):
    """
    Mimic a justification landing on ``root``: the justified checkpoint
    advances one height and the chain stays within its height band, so the
    forkchoice root of the FG frame is ``root``.
    """
    height = spec.Height(store.justified_checkpoint.height + 1)
    store.justified_checkpoint = spec.HeightCheckpoint(height=height, root=root)
    store.max_height = spec.Height(height + 1)
    assert spec.get_fg_frame(store).forkchoice_root.root == root


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_fresh_safe_quorum_with_ancestor_grade(spec, state):
    # The healthy fast-finality shape: justification lands per block, so the
    # forkchoice root is fresher than the once-per-round grade. The trailing
    # grade is outside the viable subtree but must still count as a fresh
    # quorum.
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)
    roots = apply_empty_blocks(spec, state, store, 3)
    set_justified(spec, store, roots[2])
    store.grade_2 = pending_node(spec, roots[0])

    fg_frame = spec.get_fg_frame(store)
    assert spec.get_active_prefix(store, fg_frame, store.grade_2) is None
    assert spec.has_fresh_safe_quorum(store)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_fresh_safe_quorum_with_descendant_grade(spec, state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)
    roots = apply_empty_blocks(spec, state, store, 2)
    store.grade_2 = pending_node(spec, roots[1])

    assert spec.has_fresh_safe_quorum(store)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_fresh_safe_quorum_without_grade(spec, state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)
    apply_empty_blocks(spec, state, store, 1)

    assert store.grade_2 is None
    assert not spec.has_fresh_safe_quorum(store)


@with_eip8453_and_later
@spec_state_test_with_matching_config
def test_fresh_safe_quorum_with_conflicting_grade(spec, state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)
    fork_state = state.copy()
    roots = apply_empty_blocks(spec, state, store, 3)
    set_justified(spec, store, roots[2])

    # A sibling chain that skips a slot, so its block conflicts with the
    # forkchoice root's chain
    next_slot(spec, fork_state)
    fork_block = build_empty_block_for_next_slot(spec, fork_state)
    signed_fork_block = state_transition_and_sign_block(spec, fork_state, fork_block)
    spec.on_block(store, signed_fork_block)
    store.grade_2 = pending_node(spec, fork_block.hash_tree_root())

    assert not spec.has_fresh_safe_quorum(store)
