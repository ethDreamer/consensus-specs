# EIP-8453 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Time](#time)
- [Configs](#configs)
  - [Time parameters](#time-parameters)
  - [Misc](#misc)
- [Helpers](#helpers)
  - [Modified `Store`](#modified-store)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
  - [New `get_head_vote_due_ms`](#new-get_head_vote_due_ms)
  - [New `get_support_cutoff_ms`](#new-get_support_cutoff_ms)
  - [New `get_view_freeze_ms`](#new-get_view_freeze_ms)
  - [New `is_ancestor_root`](#new-is_ancestor_root)
  - [New `is_strict_ancestor_root`](#new-is_strict_ancestor_root)
  - [New `get_deepest_node`](#new-get_deepest_node)
  - [New `is_compatible`](#new-is_compatible)
  - [New `get_subtree`](#new-get_subtree)
  - [New `get_pulled_up_state`](#new-get_pulled_up_state)
  - [Finality gadget](#finality-gadget)
    - [New `FGFrame`](#new-fgframe)
    - [New `get_fg_frame`](#new-get_fg_frame)
    - [New `get_viable_subtree`](#new-get_viable_subtree)
    - [New `is_fg_contest`](#new-is_fg_contest)
    - [New `is_fg_viable_block`](#new-is_fg_viable_block)
    - [New `has_viable_descendant`](#new-has_viable_descendant)
  - [Available chain](#available-chain)
    - [New `ACVote`](#new-acvote)
    - [New `get_ac_vote`](#new-get_ac_vote)
    - [New `get_head_vote_committee_seats_count`](#new-get_head_vote_committee_seats_count)
    - [New `get_validator_seats_count`](#new-get_validator_seats_count)
    - [New `get_block_and_payload_receipt_time`](#new-get_block_and_payload_receipt_time)
    - [New `get_vote_resolution_time`](#new-get_vote_resolution_time)
    - [New `get_local_view_from_p2p_messages`](#new-get_local_view_from_p2p_messages)
    - [New `get_view_from_blocks`](#new-get_view_from_blocks)
    - [New `get_local_view_from_blocks`](#new-get_local_view_from_blocks)
    - [New `get_proposer_view`](#new-get_proposer_view)
    - [New `compute_merged_view`](#new-compute_merged_view)
    - [New `get_combined_local_view`](#new-get_combined_local_view)
    - [New `get_equivocating_indices`](#new-get_equivocating_indices)
    - [New `get_live_locks`](#new-get_live_locks)
    - [New `compute_ghost_head`](#new-compute_ghost_head)
    - [New `compute_head_walk_score`](#new-compute_head_walk_score)
    - [New `is_eligible_for_head_walk`](#new-is_eligible_for_head_walk)
    - [New `get_head_walk_anchor`](#new-get_head_walk_anchor)
    - [New `get_head_in_tree`](#new-get_head_in_tree)
    - [New `get_voter_subtree`](#new-get_voter_subtree)
    - [New `compute_confirmation_score`](#new-compute_confirmation_score)
    - [New `get_confirmed_head`](#new-get_confirmed_head)
    - [New `compute_confirmed_path_and_lock`](#new-compute_confirmed_path_and_lock)
    - [New `compute_fast_path_and_lock`](#new-compute_fast_path_and_lock)
    - [New `compute_slow_lock`](#new-compute_slow_lock)
  - [Stabilization](#stabilization)
    - [New `StoreSafeVote`](#new-storesafevote)
    - [New `get_node_parent`](#new-get_node_parent)
    - [New `get_window_safe_votes`](#new-get_window_safe_votes)
    - [New `get_safe_vote_resolution_time_ms`](#new-get_safe_vote_resolution_time_ms)
    - [New `safe_vote_covers`](#new-safe_vote_covers)
    - [New `has_safe_vote_equivocation`](#new-has_safe_vote_equivocation)
    - [New `supports_node`](#new-supports_node)
    - [New `opposes_node`](#new-opposes_node)
    - [New `has_relative_majority`](#new-has_relative_majority)
    - [New `compute_graded_node`](#new-compute_graded_node)
    - [New `update_grades`](#new-update_grades)
    - [New `get_active_prefix`](#new-get_active_prefix)
    - [New `get_sg_anchor`](#new-get_sg_anchor)
    - [New `is_grade_0_compatible`](#new-is_grade_0_compatible)
    - [New `get_stable_root`](#new-get_stable_root)
    - [New `get_safe_vote_node`](#new-get_safe_vote_node)
    - [New `advance_record`](#new-advance_record)
    - [New `get_stable`](#new-get_stable)
  - [Store mutators](#store-mutators)
    - [New `update_finality`](#new-update_finality)
    - [New `add_lock`](#new-add_lock)
    - [New `update_locks_and_confirmation`](#new-update_locks_and_confirmation)
    - [New `record_block_receipt_time`](#new-record_block_receipt_time)
    - [New `record_payload_receipt_time`](#new-record_payload_receipt_time)
    - [New `record_head_vote_committee`](#new-record_head_vote_committee)
    - [New `record_head_vote_message`](#new-record_head_vote_message)
    - [New `record_safe_vote`](#new-record_safe_vote)
    - [New `update_sg_lock`](#new-update_sg_lock)
    - [New `update_stable_record`](#new-update_stable_record)
  - [`on_tick` helpers](#on_tick-helpers)
    - [New `update_confirmation`](#new-update_confirmation)
    - [New `unlock`](#new-unlock)
  - [`on_head_vote_message` helpers](#on_head_vote_message-helpers)
    - [New `is_valid_head_vote_message`](#new-is_valid_head_vote_message)
- [Handlers](#handlers)
  - [Modified `on_tick`](#modified-on_tick)
  - [Modified `on_block`](#modified-on_block)
  - [Modified `on_execution_payload_envelope`](#modified-on_execution_payload_envelope)
  - [New `on_head_vote_message`](#new-on_head_vote_message)
  - [New `on_safe_vote`](#new-on_safe_vote)
- [Internal API](#internal-api)
  - [New `get_ac_proposal`](#new-get_ac_proposal)
  - [New `get_ac_vote_head`](#new-get_ac_vote_head)
  - [New `get_ac_frame`](#new-get_ac_frame)
  - [FG attestation sources](#fg-attestation-sources)
    - [New `get_fg_target_source`](#new-get_fg_target_source)
    - [New `get_fg_finality_source`](#new-get_fg_finality_source)
    - [New `has_fresh_safe_quorum`](#new-has_fresh_safe_quorum)
  - [New `get_confirmed_execution_block_hash`](#new-get_confirmed_execution_block_hash)
- [External API](#external-api)
  - [New `get_confirmed_node`](#new-get_confirmed_node)
  - [Modified `get_head`](#modified-get_head)

<!-- mdformat-toc end -->

## Introduction

This document specifies the fork choice store and handlers accompanying the
[EIP-8453 upgrade](./beacon-chain.md), building on
[Heze](../../heze/fork-choice.md).

## Constants

### Time

| Name               | Value        |
| ------------------ | ------------ |
| `INFINITE_TIME_MS` | `UINT64_MAX` |

## Configs

### Time parameters

| Name                 | Value          | Duration                  |
| -------------------- | -------------- | ------------------------- |
| `HEAD_VOTE_DUE_BPS`  | `Uint64(2500)` | 25% of `SLOT_DURATION_MS` |
| `SUPPORT_CUTOFF_BPS` | `Uint64(5000)` | 50% of `SLOT_DURATION_MS` |
| `VIEW_FREEZE_BPS`    | `Uint64(7500)` | 75% of `SLOT_DURATION_MS` |

### Misc

| Name               | Value        | Description                        |
| ------------------ | ------------ | ---------------------------------- |
| `SLOW_LOCK_WINDOW` | `Slot(2**2)` | Slow-confirmation window, in slots |

## Helpers

### Modified `Store`

```python
@dataclass
class Store:
    time_ms: Uint64
    genesis_time_ms: Uint64
    # [Modified in EIP8453]
    justified_checkpoint: HeightCheckpoint
    finalized_checkpoint: HeightCheckpoint
    # [Modified in EIP8453]
    # Removed `unrealized_justified_checkpoint`
    # [Modified in EIP8453]
    # Removed `unrealized_finalized_checkpoint`
    proposer_boost_root: Root
    # [Modified in EIP8453]
    # Removed `equivocating_indices`
    blocks: dict[Root, BeaconBlock]
    block_states: dict[Root, BeaconState]
    # [Modified in EIP8453]
    # Removed `block_timeliness`
    # [Modified in EIP8453]
    # Removed `checkpoint_states`
    latest_messages: dict[ValidatorIndex, LatestMessage]
    # [Modified in EIP8453]
    # Removed `unrealized_justifications`
    payloads: dict[Root, ExecutionPayloadEnvelope]
    payload_timeliness_vote: dict[Root, list[Boolean | None]]
    payload_data_availability_vote: dict[Root, list[Boolean | None]]
    payload_inclusion_list_satisfaction: dict[Root, bool]
    # [New in EIP8453]
    max_height: Height
    block_receipt_times: dict[Root, Uint64]
    payload_receipt_times: dict[Root, Uint64]
    fast_confirmed_path: set[ForkChoiceNode]
    latest_confirmed: ForkChoiceNode
    saved_confirmations: dict[Slot, ForkChoiceNode]
    locks: dict[Uint64, ForkChoiceNode]
    head_vote_messages: dict[Slot, list[HeadVoteMessage]]
    head_vote_message_receipt_times: dict[Root, Uint64]
    head_vote_committees: dict[Slot, HeadVoteCommittee]
    safe_votes: dict[Round, list[StoreSafeVote]]
    grade_2: ForkChoiceNode | None
    grade_1: ForkChoiceNode | None
    grade_0: ForkChoiceNode | None
    grade_2_round: Round
    grade_1_round: Round
    grade_0_round: Round
    latest_stable: ForkChoiceNode
```

### Modified `get_forkchoice_store`

*Note*: The caller trusts the anchor block as justified and finalized at its
post-state’s target height.

```python
def get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock) -> Store:
    assert anchor_block.state_root == hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block)
    # [New in EIP8453]
    advanced_anchor_state = anchor_state.copy()
    process_slot(advanced_anchor_state)
    assert advanced_anchor_state.target_checkpoint.root == anchor_root
    # [Modified in EIP8453]
    anchor_height = anchor_state.target_checkpoint.height
    justified_checkpoint = HeightCheckpoint(height=anchor_height, root=anchor_root)
    finalized_checkpoint = HeightCheckpoint(height=anchor_height, root=anchor_root)
    genesis_time_ms = seconds_to_milliseconds(anchor_state.genesis_time)
    time_ms = compute_time_at_slot_ms(genesis_time_ms, anchor_state.slot)
    return Store(
        time_ms=time_ms,
        genesis_time_ms=genesis_time_ms,
        # [Modified in EIP8453]
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        proposer_boost_root=Root(),
        blocks={anchor_root: anchor_block.copy()},
        block_states={anchor_root: anchor_state.copy()},
        latest_messages={},
        payloads={},
        payload_timeliness_vote={anchor_root: [None] * PTC_SIZE},
        payload_data_availability_vote={anchor_root: [None] * PTC_SIZE},
        payload_inclusion_list_satisfaction={},
        # [New in EIP8453]
        max_height=anchor_height,
        block_receipt_times={anchor_root: time_ms},
        payload_receipt_times={},
        fast_confirmed_path=set(),
        latest_confirmed=ForkChoiceNode(
            root=finalized_checkpoint.root, payload_status=PAYLOAD_STATUS_PENDING
        ),
        saved_confirmations={},
        locks={},
        head_vote_messages={},
        head_vote_message_receipt_times={},
        head_vote_committees={},
        safe_votes={},
        grade_2=None,
        grade_1=None,
        grade_0=None,
        grade_2_round=GENESIS_ROUND,
        grade_1_round=GENESIS_ROUND,
        grade_0_round=GENESIS_ROUND,
        latest_stable=ForkChoiceNode(
            root=finalized_checkpoint.root, payload_status=PAYLOAD_STATUS_PENDING
        ),
    )
```

### New `get_head_vote_due_ms`

```python
def get_head_vote_due_ms() -> Uint64:
    return get_slot_component_duration_ms(HEAD_VOTE_DUE_BPS)
```

### New `get_support_cutoff_ms`

```python
def get_support_cutoff_ms() -> Uint64:
    return get_slot_component_duration_ms(SUPPORT_CUTOFF_BPS)
```

### New `get_view_freeze_ms`

```python
def get_view_freeze_ms() -> Uint64:
    return get_slot_component_duration_ms(VIEW_FREEZE_BPS)
```

### New `is_ancestor_root`

```python
def is_ancestor_root(store: Store, root: Root, ancestor: Root) -> bool:
    """
    Return ``True`` if ``ancestor`` is an ancestor of ``root``
    in the tree of beacon blocks ignoring payload status.
    """
    node = ForkChoiceNode(root=root, payload_status=PAYLOAD_STATUS_PENDING)
    ancestor_node = ForkChoiceNode(root=ancestor, payload_status=PAYLOAD_STATUS_PENDING)
    return is_ancestor(store, node, ancestor_node)
```

### New `is_strict_ancestor_root`

```python
def is_strict_ancestor_root(store: Store, root: Root, ancestor: Root) -> bool:
    """
    Return ``True`` if ``ancestor`` is a strict ancestor of ``root``.
    """
    return root != ancestor and is_ancestor_root(store, root, ancestor)
```

### New `get_deepest_node`

```python
def get_deepest_node(store: Store, nodes: set[ForkChoiceNode]) -> ForkChoiceNode:
    """
    Return the node in ``nodes`` with the highest slot and payload status.
    """
    assert len(nodes) > 0
    return max(
        nodes,
        key=lambda node: (
            store.blocks[node.root].slot,
            # Precedence of full/empty over pending
            0 if node.payload_status == PAYLOAD_STATUS_PENDING else 1,
        ),
    )
```

### New `is_compatible`

```python
def is_compatible(store: Store, node_1: ForkChoiceNode, node_2: ForkChoiceNode) -> bool:
    """
    Return ``True`` if ``node_1`` and ``node_2`` belong to the same chain.
    """
    if get_deepest_node(store, {node_1, node_2}) == node_1:
        return is_ancestor(store, node_1, node_2)
    else:
        return is_ancestor(store, node_2, node_1)
```

### New `get_subtree`

```python
def get_subtree(store: Store, subtree_root: ForkChoiceNode) -> Sequence[ForkChoiceNode]:
    """
    Return the nodes in a subtree rooted at ``subtree_root``, including ``subtree_root``.
    """
    subtree = [subtree_root]
    for child in get_node_children(store, subtree_root):
        subtree.extend(get_subtree(store, child))
    return subtree
```

### New `get_pulled_up_state`

```python
def get_pulled_up_state(store: Store, block_root: Root) -> BeaconState:
    """
    Return the state of the block pulled up to the current epoch if needed.
    """
    block_state = store.block_states[block_root]
    if get_current_epoch(block_state) < get_current_store_epoch(store):
        pulled_up_state = block_state.copy()
        process_slots(pulled_up_state, compute_start_slot_at_epoch(get_current_store_epoch(store)))
        return pulled_up_state
    else:
        return block_state
```

### Finality gadget

#### New `FGFrame`

*Note*: Available Chain uses the Finality Gadget frame to constrain its decision
walks.

```python
@dataclass
class FGFrame:
    finalized_node: ForkChoiceNode
    forkchoice_root: ForkChoiceNode
    tree: Sequence[ForkChoiceNode]
    viable_heads: set[ForkChoiceNode]
```

#### New `get_fg_frame`

```python
def get_fg_frame(store: Store) -> FGFrame:
    finalized_node = ForkChoiceNode(
        root=store.finalized_checkpoint.root,
        payload_status=PAYLOAD_STATUS_PENDING,
    )

    # Root the subtree at the finalized node
    tree = get_subtree(store, finalized_node)

    # Compute the forkchoice_root based on the justification height and FG contest
    if store.max_height == store.justified_checkpoint.height + 1 and not is_fg_contest(store):
        forkchoice_block_root = store.justified_checkpoint.root
    else:
        forkchoice_block_root = store.finalized_checkpoint.root
    forkchoice_root = ForkChoiceNode(
        root=forkchoice_block_root,
        payload_status=PAYLOAD_STATUS_PENDING,
    )

    # Viable nodes must be descendants of forkchoice_root and pass the FG viability test
    viable_heads = {
        node
        for node in tree
        if is_ancestor(store, node, forkchoice_root) and is_fg_viable_block(store, node.root)
    }

    return FGFrame(
        finalized_node=finalized_node,
        forkchoice_root=forkchoice_root,
        tree=tree,
        viable_heads=viable_heads,
    )
```

#### New `get_viable_subtree`

```python
def get_viable_subtree(
    store: Store, fg_frame: FGFrame, tree: Sequence[ForkChoiceNode]
) -> Sequence[ForkChoiceNode]:
    """
    Return a subtree of ``tree`` that passes the viability test.
    """
    viable_heads_in_tree = set(tree) & fg_frame.viable_heads
    return [
        node
        for node in tree
        # Nodes must be descendants of forkchoice_root
        # and ancestors of at least one viable head belonging to the tree
        if is_ancestor(store, node, fg_frame.forkchoice_root)
        and any(is_ancestor(store, viable_head, node) for viable_head in viable_heads_in_tree)
    ]
```

#### New `is_fg_contest`

*Note*: FG contest occurs when the maximum known height is exactly one above the
justified checkpoint height, and a block at that maximum height extends the
finalized checkpoint but conflicts with the justified checkpoint.

```python
def is_fg_contest(store: Store) -> bool:
    """
    Return ``True`` if ``store`` is in an FG contest.
    """
    if store.max_height > store.justified_checkpoint.height + 1:
        return False
    max_height_blocks = [
        root
        for root in store.blocks
        if store.block_states[root].target_checkpoint.height == store.max_height
        and is_ancestor_root(store, root, store.finalized_checkpoint.root)
    ]
    return any(
        not is_ancestor_root(store, b, store.justified_checkpoint.root) for b in max_height_blocks
    )
```

#### New `is_fg_viable_block`

*Note*: The height floor depends on whether there is FG contest or not.

```python
def is_fg_viable_block(store: Store, block_root: Root) -> bool:
    """
    Return ``True`` if block passes the height floor check.
    """
    block_target = store.block_states[block_root].target_checkpoint
    if is_fg_contest(store):
        return block_target.height >= store.max_height
    else:
        return block_target.height + 1 >= store.max_height
```

#### New `has_viable_descendant`

```python
def has_viable_descendant(store: Store, block_root: Root) -> bool:
    """
    Return ``True`` if the block or any of its descendants passes the FG viability check.
    """
    return any(
        is_fg_viable_block(store, root)
        for root in store.blocks
        if is_ancestor_root(store, root, block_root)
    )
```

### Available chain

#### New `ACVote`

*Note*: Represents an individual AC vote in a form suitable for set operations,
including deduplication and merging votes from messages and blocks.

```python
@dataclass(eq=True, frozen=True)
class ACVote:
    slot: Slot
    validator_index: ValidatorIndex
    supported_node: ForkChoiceNode
```

#### New `get_ac_vote`

```python
def get_ac_vote(validator_index: ValidatorIndex, data: HeadVoteData) -> ACVote:
    """
    Create an AC vote for ``validator_index`` from the head vote ``data``.
    """
    supported_node = ForkChoiceNode(
        root=data.beacon_block_root,
        payload_status=data.payload_status,
    )
    return ACVote(
        slot=data.slot,
        validator_index=validator_index,
        supported_node=supported_node,
    )
```

#### New `get_head_vote_committee_seats_count`

```python
def get_head_vote_committee_seats_count() -> Uint64:
    """
    Return size of the head vote committee.
    """
    return HEAD_VOTE_COMMITTEE_SIZE
```

#### New `get_validator_seats_count`

*Note*: The head vote committee selection may assign multiple seats to the same
validator.

```python
def get_validator_seats_count(store: Store, slot: Slot, validator_index: ValidatorIndex) -> Uint64:
    """
    Return the number of seats assigned to ``validator_index`` in the head vote committee for ``slot``.
    """
    assert slot in store.head_vote_committees
    return Uint64(store.head_vote_committees[slot].count(validator_index))
```

#### New `get_block_and_payload_receipt_time`

*Note*: An *empty* or *pending* node uses the beacon block’s receipt time. A
*full* node uses the later of the beacon block and payload receipt times.

```python
def get_block_and_payload_receipt_time(store: Store, node: ForkChoiceNode) -> Uint64:
    """
    Return ``node`` receipt time.
    """
    if node.payload_status == PAYLOAD_STATUS_FULL:
        return max(store.block_receipt_times[node.root], store.payload_receipt_times[node.root])
    else:
        return store.block_receipt_times[node.root]
```

#### New `get_vote_resolution_time`

*Note*: For unresolved votes `INFINITE_TIME_MS` is returned.

```python
def get_vote_resolution_time(
    store: Store, supported_node: ForkChoiceNode, vote_slot: Slot, vote_receipt_time: Uint64
) -> Uint64:
    """
    Return the resolution time of the vote.
    """
    block_root = supported_node.root
    payload_status = supported_node.payload_status

    # Votes must be for a known block
    if block_root not in store.blocks:
        return INFINITE_TIME_MS

    # The supported block must not be later than the vote's slot
    block_slot = store.blocks[block_root].slot
    if block_slot > vote_slot:
        return INFINITE_TIME_MS

    # Votes for a block in the vote's own slot must support PENDING
    if block_slot == vote_slot and payload_status != PAYLOAD_STATUS_PENDING:
        return INFINITE_TIME_MS

    # Full votes require a verified payload
    if payload_status == PAYLOAD_STATUS_FULL and not is_payload_verified(store, block_root):
        return INFINITE_TIME_MS

    # Votes must support blocks belonging to the FG frame
    if not is_ancestor_root(store, supported_node.root, store.finalized_checkpoint.root):
        return INFINITE_TIME_MS

    return max(vote_receipt_time, get_block_and_payload_receipt_time(store, supported_node))
```

#### New `get_local_view_from_p2p_messages`

*Note*: Builds an AC view from P2P messages using locally observed receipt and
resolution times.

```python
def get_local_view_from_p2p_messages(
    store: Store, vote_slot: Slot, receipt_threshold_ms: Uint64, resolution_threshold_ms: Uint64
) -> tuple[list[HeadVoteMessage], list[int]]:
    """
    Return messages for ``vote_slot`` received before ``receipt_threshold_ms``,
    and indices of those votes that are resolved before ``resolution_threshold_ms``.
    """
    vote_messages: list[HeadVoteMessage] = []
    support_indices: list[int] = []

    for index, message in enumerate(store.head_vote_messages.get(vote_slot, [])):
        data = message.data
        message_root = hash_tree_root(message)
        message_receipt_ms = store.head_vote_message_receipt_times[message_root]
        # Include messages received before the receipt threshold
        if message_receipt_ms < receipt_threshold_ms:
            vote_messages.append(message)
            supported_node = ForkChoiceNode(
                root=data.beacon_block_root, payload_status=data.payload_status
            )
            # Record the indices of included messages whose votes resolve before the support threshold
            if (
                get_vote_resolution_time(store, supported_node, data.slot, message_receipt_ms)
                < resolution_threshold_ms
            ):
                support_indices.append(index)

    return vote_messages, support_indices
```

#### New `get_view_from_blocks`

*Note*: A general function to build AC view from votes included in blocks.

```python
def get_view_from_blocks(
    store: Store,
    block_slot: Slot,
    vote_slot: Slot,
    block_predicate: Callable[[Root], bool],
    get_supporting_indices: Callable[[Root, HeadVote, HeadVoteSupportBits], set[int]],
) -> tuple[list[HeadVote], list[set[int]]]:
    """
    Return head votes for ``vote_slot`` included in blocks at ``block_slot``
    that pass ``block_predicate`` and indices of supporting votes
    obtained via ``get_supporting_indices``.
    """
    vote_messages: list[HeadVote] = []
    support_positions: list[set[int]] = []

    for block_root in store.blocks:
        block = store.blocks[block_root]
        # Filter by block slot and block test predicate
        if block.slot == block_slot and block_predicate(block_root):
            for vote_index, head_vote in enumerate(block.body.head_votes):
                data = head_vote.data
                # Filter by the vote slot
                if data.slot == vote_slot:
                    vote_messages.append(head_vote)
                    support_bits = block.body.head_vote_support[vote_index]
                    support_positions.append(
                        get_supporting_indices(block_root, head_vote, support_bits)
                    )

    return vote_messages, support_positions
```

#### New `get_local_view_from_blocks`

*Note*: Builds an AC view from block votes using locally observed receipt and
resolution times.

```python
def get_local_view_from_blocks(
    store: Store, vote_slot: Slot, receipt_threshold_ms: Uint64, resolution_threshold_ms: Uint64
) -> tuple[list[HeadVote], list[set[int]]]:
    """
    Return votes for ``vote_slot`` indluded in blocks received before ``receipt_threshold_ms``,
    and indices of those votes that are resolved before ``resolution_threshold_ms``.
    """

    def get_supporting_indices(
        block_root: Root, head_vote: HeadVote, _support_bits: HeadVoteSupportBits
    ) -> set[int]:
        data = head_vote.data
        block_receipt_time = store.block_receipt_times[block_root]
        supported_node = ForkChoiceNode(
            root=data.beacon_block_root, payload_status=data.payload_status
        )
        if (
            get_vote_resolution_time(store, supported_node, data.slot, block_receipt_time)
            < resolution_threshold_ms
        ):
            # All voters in this vote support the locally resolved node
            return {*range(len(head_vote.voter_indices))}
        else:
            return set()

    # Restrict to blocks that are from the slot immediately after the vote slot
    return get_view_from_blocks(
        store,
        vote_slot + 1,
        vote_slot,
        block_predicate=lambda block_root: (
            store.block_receipt_times[block_root] < receipt_threshold_ms
        ),
        get_supporting_indices=get_supporting_indices,
    )
```

#### New `get_proposer_view`

*Note*: Builds an AC proposer view. Supporting votes must reference locally
known blocks; *full* block support additionally requires a verified payload.

```python
def get_proposer_view(
    store: Store, block_slot: Slot, vote_slot: Slot
) -> tuple[list[HeadVote], list[set[int]]]:
    """
    Return the proposer view for ``vote_slot`` from proposals made in ``block_slot``.
    """

    def get_supporting_indices(
        _block_root: Root, head_vote: HeadVote, support_bits: HeadVoteSupportBits
    ) -> set[int]:
        data = head_vote.data
        # Supporting subset must support a locally known block with correct block's slot
        # and matching payload status
        if (
            data.beacon_block_root in store.blocks
            and (
                store.blocks[data.beacon_block_root].slot < vote_slot
                or data.payload_status == PAYLOAD_STATUS_PENDING
            )
            and store.blocks[data.beacon_block_root].slot <= vote_slot
            and (
                data.payload_status != PAYLOAD_STATUS_FULL
                or is_payload_verified(store, data.beacon_block_root)
            )
        ):
            return {position for position, is_support in enumerate(support_bits) if is_support}
        else:
            return set()

    return get_view_from_blocks(
        store,
        block_slot,
        vote_slot,
        block_predicate=lambda block_root: is_ancestor_root(
            store, block_root, store.finalized_checkpoint.root
        ),
        get_supporting_indices=get_supporting_indices,
    )
```

#### New `compute_merged_view`

*Note*: Merges views from P2P messages and blocks into sets of single AC votes,
deduplicating votes and combining their support.

```python
def compute_merged_view(
    votes_from_messages: tuple[list[HeadVoteMessage], list[int]],
    votes_from_blocks: tuple[list[HeadVote], list[set[int]]],
) -> tuple[set[ACVote], set[ACVote]]:
    """
    Return the merged vote set and its supporting subset.
    """
    votes: set[ACVote] = set()
    support_votes: set[ACVote] = set()

    # Process p2p message votes
    for index, message_vote in enumerate(votes_from_messages[0]):
        vote = get_ac_vote(message_vote.validator_index, message_vote.data)
        votes.add(vote)
        if index in votes_from_messages[1]:
            support_votes.add(vote)

    # Update sets with block votes
    for vote_index, block_vote in enumerate(votes_from_blocks[0]):
        support_positions = votes_from_blocks[1][vote_index]
        for position, voter_index in enumerate(block_vote.voter_indices):
            vote = get_ac_vote(voter_index, block_vote.data)
            votes.add(vote)
            if position in support_positions:
                support_votes.add(vote)

    return votes, support_votes
```

#### New `get_combined_local_view`

```python
def get_combined_local_view(
    store: Store, slot: Slot, receipt_threshold_ms: Uint64, resolution_threshold_ms: Uint64
) -> tuple[set[ACVote], set[ACVote]]:
    """
    Return the merged local vote set and supporting subset for ``slot``,
    using the receipt and resolution thresholds for both P2P and block votes.
    """
    votes_from_messages = get_local_view_from_p2p_messages(
        store, slot, receipt_threshold_ms, resolution_threshold_ms
    )
    votes_from_blocks = get_local_view_from_blocks(
        store, slot, receipt_threshold_ms, resolution_threshold_ms
    )
    return compute_merged_view(votes_from_messages, votes_from_blocks)
```

#### New `get_equivocating_indices`

```python
def get_equivocating_indices(votes: set[ACVote]) -> set[ValidatorIndex]:
    """
    Return indices of validators with multiple distinct votes.
    """
    equivocating_indices: set[ValidatorIndex] = set()
    for voter_index in {vote.validator_index for vote in votes}:
        votes_by_index = {vote for vote in votes if vote.validator_index == voter_index}
        if len(votes_by_index) > 1:
            equivocating_indices.add(voter_index)
    return equivocating_indices
```

#### New `get_live_locks`

```python
def get_live_locks(
    store: Store, fg_frame: FGFrame, time_ms: Uint64
) -> list[tuple[Uint64, ForkChoiceNode]]:
    """
    Return (deadline, node) tuples for unexpired locks in ``fg_frame.tree``.
    """
    return [
        (deadline, lock)
        for deadline, lock in store.locks.items()
        if deadline > time_ms and lock in fg_frame.tree
    ]
```

#### New `compute_ghost_head`

```python
def compute_ghost_head(
    store: Store,
    anchor: ForkChoiceNode,
    tree: Sequence[ForkChoiceNode],
    get_score: Callable[[ForkChoiceNode], Uint64],
    is_eligible: Callable[[ForkChoiceNode], bool],
) -> ForkChoiceNode:
    """
    Return the head reached by a GHOST walk from ``anchor``,
    using the supplied scoring and eligibility functions.
    """
    head = anchor
    while True:
        eligible_children = [
            child
            for child in get_node_children(store, head)
            if child in tree and is_eligible(child)
        ]
        if len(eligible_children) == 0:
            return head
        head = max(
            eligible_children,
            key=lambda child: (
                get_score(child),
                child.root,
                get_payload_status_tiebreaker(store, child),
            ),
        )
```

#### New `compute_head_walk_score`

*Note*: Equivocating validators contribute their support to every node. The
node’s supporting score counts the committee seats of non-equivocating
validators whose support vote is for the node or one of its descendants.

```python
def compute_head_walk_score(
    store: Store,
    votes: set[ACVote],
    support_votes: set[ACVote],
    slot: Slot,
    node: ForkChoiceNode,
) -> Uint64:
    """
    Return the sum of the equivocating score and the node's supporting score.
    """
    equivocating_indices = get_equivocating_indices(votes)
    # Votes for any descendant from the support set
    # cast by non-equivocating voters of a given slot
    supporting_indices = {
        vote.validator_index
        for vote in support_votes
        if vote.validator_index not in equivocating_indices
        and vote.slot == slot
        and is_ancestor(store, vote.supported_node, node)
    }
    equivocating_score = Uint64(
        sum(
            get_validator_seats_count(store, slot, validator_index)
            for validator_index in equivocating_indices
        )
    )
    supporting_score = Uint64(
        sum(
            get_validator_seats_count(store, slot, validator_index)
            for validator_index in supporting_indices
        )
    )
    # Equivocating score counts for every block
    return equivocating_score + supporting_score
```

#### New `is_eligible_for_head_walk`

*Note*: A node is eligible for the head walk if it is a full or empty node from
the previous slot, its parent block is not yet a viable head, its block is from
the current slot, or its head-walk score exceeds half the participating
committee seats.

```python
def is_eligible_for_head_walk(
    store: Store,
    fg_frame: FGFrame,
    votes: set[ACVote],
    support_votes: set[ACVote],
    slot: Slot,
    node: ForkChoiceNode,
) -> bool:
    """
    Return ``True`` if the head walk may advance into ``node``.
    """
    block = store.blocks[node.root]

    # Full or empty nodes from the previous slot are always eligible
    if is_previous_slot_payload_decision(store, node):
        return True

    parent = ForkChoiceNode(root=block.parent_root, payload_status=PAYLOAD_STATUS_PENDING)
    if parent not in fg_frame.viable_heads:
        return True

    if block.slot == get_current_slot(store):
        return True

    # Total seats of all voters
    voting_indices = {vote.validator_index for vote in votes}
    voting_seats_count = Uint64(
        sum(
            get_validator_seats_count(store, slot, validator_index)
            for validator_index in voting_indices
        )
    )
    score = compute_head_walk_score(store, votes, support_votes, slot, node)

    # Require a strict majority of participating committee seats
    return 2 * score > voting_seats_count
```

#### New `get_head_walk_anchor`

*Note*: The anchor is the deepest locked node in the full viable subtree of the
FG frame, or the forkchoice root if no such node exists. Ancestors of live lock
tips are also considered locked.

```python
def get_head_walk_anchor(store: Store, fg_frame: FGFrame) -> ForkChoiceNode:
    """
    Return the head-walk anchor.
    """
    live_locks = get_live_locks(store, fg_frame, store.time_ms)
    locked_viable_nodes = {
        node
        for node in get_viable_subtree(store, fg_frame, fg_frame.tree)
        if any(is_ancestor(store, lock, node) for _, lock in live_locks)
    }

    # Set anchor to the deepest locked viable node if exists,
    # otherwise, fork choice root
    if len(locked_viable_nodes) > 0:
        return get_deepest_node(store, locked_viable_nodes)
    else:
        return fg_frame.forkchoice_root
```

#### New `get_head_in_tree`

*Note*: Walks the viable subtree of tree from the head-walk anchor, using the
head-walk scoring and eligibility rules. The anchor is selected from the full FG
frame independently of tree.

```python
def get_head_in_tree(
    store: Store,
    fg_frame: FGFrame,
    tree: Sequence[ForkChoiceNode],
    votes: set[ACVote],
    support_votes: set[ACVote],
    slot: Slot,
) -> ForkChoiceNode:
    """
    Return the head of the tree.
    """
    anchor = get_head_walk_anchor(store, fg_frame)
    viable_subtree = get_viable_subtree(store, fg_frame, tree)
    return compute_ghost_head(
        store=store,
        anchor=anchor,
        tree=viable_subtree,
        get_score=lambda node: compute_head_walk_score(store, votes, support_votes, slot, node),
        is_eligible=lambda node: is_eligible_for_head_walk(
            store, fg_frame, votes, support_votes, slot, node
        ),
    )
```

#### New `get_voter_subtree`

*Note*: Return a subtree of nodes received before the previous slot's
view-freeze deadline, together with ancestors of proposals from the voting slot,
including the proposals themselves.

```python
def get_voter_subtree(
    store: Store, tree: Sequence[ForkChoiceNode], slot: Slot
) -> Sequence[ForkChoiceNode]:
    """
    Return the subtree available to the voter in ``slot``.
    """
    view_freeze_ms = compute_time_at_slot_ms(store.genesis_time_ms, slot - 1) + get_view_freeze_ms()
    slot_proposals = {node for node in tree if store.blocks[node.root].slot == slot}
    return [
        node
        for node in tree
        if get_block_and_payload_receipt_time(store, node) < view_freeze_ms
        or any(is_ancestor(store, proposal, node) for proposal in slot_proposals)
    ]
```

#### New `compute_confirmation_score`

*Note*: The confirmation score counts the committee seats of non-equivocating
validators whose votes are in support votes set and support the node or one of
its descendants. Equivocating validators contribute no support.

```python
def compute_confirmation_score(
    store: Store,
    votes: set[ACVote],
    support_votes: set[ACVote],
    slot: Slot,
    node: ForkChoiceNode,
) -> Uint64:
    """
    Return confirmation score of the ``node``.
    """
    equivocating_indices = get_equivocating_indices(votes)
    supporting_indices = {
        vote.validator_index
        for vote in support_votes
        if vote.validator_index not in equivocating_indices
        and is_ancestor(store, vote.supported_node, node)
    }
    return Uint64(
        sum(
            get_validator_seats_count(store, slot, validator_index)
            for validator_index in supporting_indices
        )
    )
```

#### New `get_confirmed_head`

*Note*: Runs a confirmation walk using the confirmation score, requiring
eligible nodes to score more than half the participating committee seats.
Returns `None` if the resulting head is ineligible, including when the walk
stops at the finalized node.

```python
def get_confirmed_head(
    store: Store, fg_frame: FGFrame, votes: set[ACVote], support_votes: set[ACVote], slot: Slot
) -> ForkChoiceNode | None:
    """
    Return the confirmation candidate, or ``None`` if no node has sufficient support.
    """
    voting_indices = {vote.validator_index for vote in votes}
    voting_seats_count = Uint64(
        sum(
            get_validator_seats_count(store, slot, validator_index)
            for validator_index in voting_indices
        )
    )

    def is_eligible(node: ForkChoiceNode) -> bool:
        return (
            2 * compute_confirmation_score(store, votes, support_votes, slot, node)
            > voting_seats_count
        )

    head = compute_ghost_head(
        store=store,
        anchor=fg_frame.finalized_node,
        tree=fg_frame.tree,
        get_score=lambda node: compute_confirmation_score(store, votes, support_votes, slot, node),
        is_eligible=is_eligible,
    )

    if is_eligible(head):
        return head
    else:
        return None
```

#### New `compute_confirmed_path_and_lock`

*Note*: Computes the confirmed path and the lock as the deepest node in the
confirmed path. Candidate nodes are selected from FG frame, genesis is excluded.

```python
def compute_confirmed_path_and_lock(
    store: Store,
    fg_frame: FGFrame,
    confirmed: ForkChoiceNode,
    test_predicate: Callable[[ForkChoiceNode], bool],
) -> tuple[set[ForkChoiceNode], ForkChoiceNode | None]:
    """
    Return the selected path nodes and their deepest node, or an empty set and ``None``.
    """
    path = {
        node
        for node in fg_frame.tree
        if is_ancestor(store, confirmed, node)
        and store.blocks[node.root].slot > GENESIS_SLOT
        and test_predicate(node)
    }

    if len(path) == 0:
        return set(), None

    # The deepest node passing the test
    lock = get_deepest_node(store, path)

    return path, lock
```

#### New `compute_fast_path_and_lock`

*Note*: Selects non-genesis nodes on the path to `confirmed` within the FG frame
whose confirmation support accounts for at least half of all committee seats.
The deepest selected node is the fast lock.

```python
def compute_fast_path_and_lock(
    store: Store,
    fg_frame: FGFrame,
    votes: set[ACVote],
    support_votes: set[ACVote],
    slot: Slot,
    confirmed: ForkChoiceNode,
) -> tuple[set[ForkChoiceNode], ForkChoiceNode | None]:
    """
    Return the fast-confirmed path and lock, or an empty set and ``None``.
    """
    return compute_confirmed_path_and_lock(
        store=store,
        fg_frame=fg_frame,
        confirmed=confirmed,
        test_predicate=lambda node: (
            2 * compute_confirmation_score(store, votes, support_votes, slot, node)
            >= get_head_vote_committee_seats_count()
        ),
    )
```

#### New `compute_slow_lock`

*Note*: The slow lock requires:

- Saved confirmations in the FG frame for each of the preceding
  `SLOW_LOCK_WINDOW - 1` slots.
- A non-genesis node in the FG frame that is an ancestor of or equal to both the
  current candidate and every saved confirmation in that window.

The deepest such node is the slow lock.

```python
def compute_slow_lock(
    store: Store, fg_frame: FGFrame, slot: Slot, confirmed: ForkChoiceNode
) -> ForkChoiceNode | None:
    """
    Return the slow lock, or ``None`` if the window or common ancestor is missing.
    """
    if slot + 1 < SLOW_LOCK_WINDOW:
        return None

    previous_slots = range(slot + 1 - SLOW_LOCK_WINDOW, slot)
    if not all(
        Slot(j) in store.saved_confirmations and store.saved_confirmations[Slot(j)] in fg_frame.tree
        for j in previous_slots
    ):
        return None

    _, slow_lock = compute_confirmed_path_and_lock(
        store=store,
        fg_frame=fg_frame,
        confirmed=confirmed,
        test_predicate=lambda node: all(
            is_ancestor(store, store.saved_confirmations[Slot(j)], node) for j in previous_slots
        ),
    )
    return slow_lock
```

### Stabilization

The stabilization rule reads the safe votes of the expiry window — the rounds
`[max(0, r − SAFE_VOTE_EXPIRY_ROUNDS), r)` — and weighs them with the FG
validator weights. A validator *supports* a node when its latest vote resolved
by the early cutoff covers the node and nothing it did by the late cutoff walks
that back; it *opposes* the node when a later vote leaves the node's chain or an
equivocation surfaces. A node holds a *relative majority* when supporting weight
strictly exceeds opposing weight: there is no absolute threshold, so the test is
meaningful at any participation level, and two conflicting nodes can never both
hold it.

*Note*: Weights are read from the latest finalized block's post-state, the same
dependent state that fixes the head vote committees.

#### New `StoreSafeVote`

```python
@dataclass(eq=True, frozen=True)
class StoreSafeVote:
    validator_index: ValidatorIndex
    data: SafeVoteData
    arrival_ms: Uint64
```

#### New `get_node_parent`

```python
def get_node_parent(store: Store, node: ForkChoiceNode) -> ForkChoiceNode | None:
    if node.payload_status != PAYLOAD_STATUS_PENDING:
        return ForkChoiceNode(root=node.root, payload_status=PAYLOAD_STATUS_PENDING)
    block = store.blocks[node.root]
    if block.parent_root not in store.blocks:
        return None
    return ForkChoiceNode(
        root=block.parent_root,
        payload_status=get_parent_payload_status(store, block),
    )
```

#### New `get_window_safe_votes`

```python
def get_window_safe_votes(store: Store, round: Round) -> Sequence[StoreSafeVote]:
    start = Round(round - min(round, SAFE_VOTE_EXPIRY_ROUNDS))
    votes: list[StoreSafeVote] = []
    for window_round in range(start, round):
        if Round(window_round) in store.safe_votes:
            votes.extend(store.safe_votes[Round(window_round)])
    return votes
```

#### New `get_safe_vote_resolution_time_ms`

*Note*: A safe vote resolves when the store holds its node's block and the block
is compatible with the finalized block. A vote for a block conflicting with the
finalized chain neither supports nor covers.

```python
def get_safe_vote_resolution_time_ms(store: Store, vote: StoreSafeVote) -> Uint64 | None:
    root = vote.data.beacon_block_root
    if root not in store.blocks:
        return None
    finalized_root = store.finalized_checkpoint.root
    is_compatible = is_ancestor_root(store, finalized_root, root) or is_ancestor_root(
        store, root, finalized_root
    )
    if not is_compatible:
        return None
    return max(vote.arrival_ms, store.block_receipt_times[root])
```

#### New `safe_vote_covers`

```python
def safe_vote_covers(store: Store, data: SafeVoteData, node: ForkChoiceNode) -> bool:
    if data.beacon_block_root not in store.blocks:
        return False
    vote_node = ForkChoiceNode(root=data.beacon_block_root, payload_status=data.payload_status)
    return is_ancestor(store, vote_node, node)
```

#### New `has_safe_vote_equivocation`

*Note*: Whether `votes` holds two distinct votes of one round at or after round
`round_floor` — the counter-evidence form of equivocation used by support and
opposition.

```python
def has_safe_vote_equivocation(votes: Sequence[StoreSafeVote], round_floor: Round) -> bool:
    seen: dict[Round, SafeVoteData] = {}
    for vote in votes:
        if vote.data.round < round_floor:
            continue
        if vote.data.round in seen:
            if seen[vote.data.round] != vote.data:
                return True
        else:
            seen[vote.data.round] = vote.data
    return False
```

#### New `supports_node`

```python
def supports_node(
    store: Store,
    window: Sequence[StoreSafeVote],
    early_ms: Uint64,
    late_ms: Uint64,
    validator_index: ValidatorIndex,
    node: ForkChoiceNode,
) -> bool:
    own_votes = [vote for vote in window if vote.validator_index == validator_index]
    received = [vote for vote in own_votes if vote.arrival_ms < late_ms]
    early_resolved = []
    late_resolved = []
    for vote in own_votes:
        resolution_ms = get_safe_vote_resolution_time_ms(store, vote)
        if resolution_ms is None:
            continue
        if resolution_ms < early_ms:
            early_resolved.append(vote)
        if resolution_ms < late_ms:
            late_resolved.append(vote)
    if len(early_resolved) == 0:
        return False
    latest = max(early_resolved, key=lambda vote: vote.data.round)
    if not safe_vote_covers(store, latest.data, node):
        return False
    if has_safe_vote_equivocation(received, latest.data.round):
        return False
    return all(
        safe_vote_covers(store, vote.data, node)
        for vote in late_resolved
        if vote.data.round > latest.data.round
    )
```

#### New `opposes_node`

```python
def opposes_node(
    store: Store,
    window: Sequence[StoreSafeVote],
    early_ms: Uint64,
    late_ms: Uint64,
    validator_index: ValidatorIndex,
    node: ForkChoiceNode,
) -> bool:
    own_votes = [vote for vote in window if vote.validator_index == validator_index]
    received = [vote for vote in own_votes if vote.arrival_ms < late_ms]
    early_rounds = []
    late_resolved = []
    for vote in own_votes:
        resolution_ms = get_safe_vote_resolution_time_ms(store, vote)
        if resolution_ms is None:
            continue
        if resolution_ms < early_ms:
            early_rounds.append(vote.data.round)
        if resolution_ms < late_ms:
            late_resolved.append(vote)
    round_floor = max(early_rounds) if len(early_rounds) > 0 else Round(0)
    has_defection = any(
        not safe_vote_covers(store, vote.data, node)
        for vote in late_resolved
        if vote.data.round >= round_floor
    )
    return has_defection or has_safe_vote_equivocation(received, round_floor)
```

#### New `has_relative_majority`

```python
def has_relative_majority(
    store: Store, round: Round, early_ms: Uint64, late_ms: Uint64, node: ForkChoiceNode
) -> bool:
    window = get_window_safe_votes(store, round)
    weight_state = store.block_states[store.finalized_checkpoint.root]
    participants: set[ValidatorIndex] = set()
    for vote in window:
        if vote.arrival_ms < late_ms:
            participants.add(vote.validator_index)
    supporting_weight = Uint256(0)
    opposing_weight = Uint256(0)
    for validator_index in participants:
        # A validator unknown to the weight state carries no weight
        if validator_index >= len(weight_state.validators):
            continue
        weight = get_validator_weight(weight_state, validator_index)
        if supports_node(store, window, early_ms, late_ms, validator_index, node):
            supporting_weight += weight
        elif opposes_node(store, window, early_ms, late_ms, validator_index, node):
            opposing_weight += weight
    return supporting_weight > opposing_weight
```

#### New `compute_graded_node`

*Note*: The nodes holding a relative majority in one store lie on one chain, so
the deepest of them is well defined; the slot orders depth, with the payload
children of a block deeper than its pending node.

```python
def compute_graded_node(
    store: Store, round: Round, early_ms: Uint64, late_ms: Uint64
) -> ForkChoiceNode | None:
    graded: list[ForkChoiceNode] = []
    statuses = (PAYLOAD_STATUS_PENDING, PAYLOAD_STATUS_EMPTY, PAYLOAD_STATUS_FULL)
    for root in store.blocks:
        for payload_status in statuses:
            node = ForkChoiceNode(root=root, payload_status=payload_status)
            if has_relative_majority(store, round, early_ms, late_ms, node):
                graded.append(node)
    if len(graded) == 0:
        return None
    return max(
        graded,
        key=lambda node: (
            store.blocks[node.root].slot,
            Uint64(0) if node.payload_status == PAYLOAD_STATUS_PENDING else Uint64(1),
            node.root,
        ),
    )
```

#### New `update_grades`

*Note*: Each grade of each round is computed once, at or after its completion
time. The cutoffs are receipt-time comparisons, so a completion evaluated late
reads the same sets a timely one would have. A node that ticks sparsely skips
the intervening rounds' grades rather than reconstructing them; the current
round's grades are always evaluated.

```python
def update_grades(store: Store) -> None:
    quarter_ms = get_head_vote_due_ms()
    current_round = compute_round_at_slot(get_current_slot(store))
    if current_round == GENESIS_ROUND:
        return
    start_ms = compute_time_at_slot_ms(
        store.genesis_time_ms, compute_start_slot_at_round(current_round)
    )
    # Grade 2 of a round completes in the last quarter-slot of the previous
    # round; a node that missed that tick evaluates it late
    if store.grade_2_round < current_round:
        store.grade_2 = compute_graded_node(
            store,
            current_round,
            Uint64(start_ms - 5 * quarter_ms),
            Uint64(start_ms - quarter_ms),
        )
        store.grade_2_round = current_round
    next_round = Round(current_round + 1)
    next_start_ms = compute_time_at_slot_ms(
        store.genesis_time_ms, compute_start_slot_at_round(next_round)
    )
    if store.time_ms + quarter_ms >= next_start_ms and store.grade_2_round < next_round:
        store.grade_2 = compute_graded_node(
            store,
            next_round,
            Uint64(next_start_ms - 5 * quarter_ms),
            Uint64(next_start_ms - quarter_ms),
        )
        store.grade_2_round = next_round
    # Grade 1 completes at the round boundary
    if store.grade_1_round < current_round:
        store.grade_1 = compute_graded_node(
            store,
            current_round,
            Uint64(start_ms - 4 * quarter_ms),
            Uint64(start_ms - 2 * quarter_ms),
        )
        store.grade_1_round = current_round
    # Grade 0 completes one quarter-slot into the round
    if store.time_ms >= start_ms + quarter_ms and store.grade_0_round < current_round:
        store.grade_0 = compute_graded_node(
            store,
            current_round,
            Uint64(start_ms - 3 * quarter_ms),
            Uint64(start_ms - 3 * quarter_ms),
        )
        store.grade_0_round = current_round
```

#### New `get_active_prefix`

*Note*: A saved grade is *active* when it has an ancestor in the viable subtree
of the FG frame, and its active prefix is the deepest such ancestor: the fork
choice can use it, and it descends the forkchoice root.

```python
def get_active_prefix(
    store: Store, fg_frame: FGFrame, node: ForkChoiceNode | None
) -> ForkChoiceNode | None:
    if node is None or node.root not in store.blocks:
        return None
    viable = get_viable_subtree(store, fg_frame, fg_frame.tree)
    current: ForkChoiceNode | None = node
    while current is not None:
        if current in viable:
            return current
        current = get_node_parent(store, current)
    return None
```

#### New `get_sg_anchor`

*Note*: The stabilization anchor: the active prefix of the saved grade-1 node,
and the forkchoice root when there is no grade-1 node or the root has passed it.
It enters the head walk as a lock through `update_sg_lock` rather than by
re-anchoring the walk.

```python
def get_sg_anchor(store: Store, fg_frame: FGFrame) -> ForkChoiceNode:
    prefix = get_active_prefix(store, fg_frame, store.grade_1)
    if prefix is not None:
        return prefix
    return fg_frame.forkchoice_root
```

#### New `is_grade_0_compatible`

```python
def is_grade_0_compatible(store: Store, node: ForkChoiceNode) -> bool:
    veto = store.grade_0
    if veto is None or veto.root not in store.blocks or node.root not in store.blocks:
        return True
    return is_compatible(store, node, veto)
```

#### New `get_stable_root`

```python
def get_stable_root(store: Store, fg_frame: FGFrame) -> ForkChoiceNode:
    prefix = get_active_prefix(store, fg_frame, store.grade_2)
    if prefix is not None:
        return prefix
    return fg_frame.forkchoice_root
```

#### New `get_safe_vote_node`

*Note*: The node an honest validator names in its safe vote: the deepest
grade-0-compatible node between the anchor and the confirmed node; the grade-2
active prefix when there is none; the forkchoice root when grade 2 exists but
the root has passed it; and the anchor as the final fallback, which keeps voting
total.

```python
def get_safe_vote_node(store: Store) -> ForkChoiceNode:
    fg_frame = get_fg_frame(store)
    anchor = get_sg_anchor(store, fg_frame)
    confirmed = get_confirmed_node(store)
    if is_ancestor(store, confirmed, anchor):
        current: ForkChoiceNode | None = confirmed
        while current is not None:
            if is_grade_0_compatible(store, current):
                return current
            if current == anchor:
                break
            current = get_node_parent(store, current)
    grade_2_prefix = get_active_prefix(store, fg_frame, store.grade_2)
    if grade_2_prefix is not None:
        return grade_2_prefix
    if store.grade_2 is not None:
        return fg_frame.forkchoice_root
    return anchor
```

#### New `advance_record`

*Note*: This is the paper's `advance`: no candidate or an ancestor candidate
leaves a record unchanged, while an extension or a conflicting candidate
replaces it. This permits recovery from a conflicting record formed in an unsafe
period.

```python
def advance_record(
    store: Store, old: ForkChoiceNode, candidate: ForkChoiceNode | None
) -> ForkChoiceNode:
    if candidate is None or candidate == old or is_ancestor(store, old, candidate):
        return old
    return candidate
```

#### New `get_stable`

*Note*: User-facing; no voting rule reads it. It backs the stable chain, one
layer above finality and one below the available chain.

```python
def get_stable(store: Store) -> ForkChoiceNode:
    finalized_root = store.finalized_checkpoint.root
    if is_ancestor_root(store, store.latest_stable.root, finalized_root):
        return store.latest_stable
    return ForkChoiceNode(root=finalized_root, payload_status=PAYLOAD_STATUS_PENDING)
```

### Store mutators

#### New `update_finality`

*Notes*: First, update the store's maximum known height using the state's target
height.

Replace the store's justified checkpoint with the state's justified checkpoint
when both conditions hold:

- Its `(height, root)` tuple is lexicographically greater than the store's
  justified tuple.
- Its block descends from or equals the store's finalized block.

Then replace the store's finalized checkpoint with the state's finalized
checkpoint when all conditions hold:

- Its height is greater than the store's finalized height.
- Its block is a strict descendant of the store's finalized block.
- Its block is an ancestor of or equal to the store's justified block, including
  any justification update made above.
- Its block or one of its descendants passes the FG viability check.

```python
def update_finality(store: Store, state: BeaconState) -> None:
    """
    Update finality gadget information in store
    """
    # Update max_height
    store.max_height = max(store.max_height, state.target_checkpoint.height)

    # Update justification
    store_justification = (store.justified_checkpoint.height, store.justified_checkpoint.root)
    state_justification = (state.justified_checkpoint.height, state.justified_checkpoint.root)
    if state_justification > store_justification and is_ancestor_root(
        store, state.justified_checkpoint.root, store.finalized_checkpoint.root
    ):
        store.justified_checkpoint = state.justified_checkpoint

    # Update finality
    if (
        state.finalized_checkpoint.height > store.finalized_checkpoint.height
        and is_strict_ancestor_root(
            store, state.finalized_checkpoint.root, store.finalized_checkpoint.root
        )
        and is_ancestor_root(
            store, store.justified_checkpoint.root, state.finalized_checkpoint.root
        )
        and has_viable_descendant(store, state.finalized_checkpoint.root)
    ):
        store.finalized_checkpoint = state.finalized_checkpoint
```

#### New `add_lock`

*Note*: Locks can have multiple producers. The fast and slow confirmation locks
below are two; other producers, such as a lock seeded at a fork transition,
register locks the same way.

```python
def add_lock(store: Store, deadline: Uint64, node: ForkChoiceNode) -> None:
    """
    Register ``node`` as a lock that expires at ``deadline``.
    """
    store.locks[deadline] = node
```

#### New `update_locks_and_confirmation`

```python
def update_locks_and_confirmation(
    store: Store,
    slot: Slot,
    fg_frame: FGFrame,
    confirmed: ForkChoiceNode,
    fast_confirmed_path: set[ForkChoiceNode],
    fast_lock: ForkChoiceNode | None,
    slow_lock: ForkChoiceNode | None,
) -> None:
    """
    Update locks and confirmed head information.
    """

    # Update fast confirmed path
    store.fast_confirmed_path = fast_confirmed_path

    # Save the confirmation for slot
    store.saved_confirmations[slot] = confirmed

    # Select the deepest node passing either test
    if fast_lock is not None and slow_lock is not None:
        lock = get_deepest_node(store, {fast_lock, slow_lock})
    elif fast_lock is not None:
        lock = fast_lock
    else:
        lock = slow_lock

    # Compute deadline and add lock
    if lock is not None:
        deadline = (
            compute_time_at_slot_ms(store.genesis_time_ms, slot + SLOW_LOCK_WINDOW + 1)
            + get_head_vote_due_ms()
        )
        add_lock(store, deadline, lock)

    # Keep latest_confirmed if it remains in the FG frame and extends or equals confirmed.
    # Otherwise, replace it with confirmed.
    if not (
        store.latest_confirmed in fg_frame.tree
        and is_ancestor(store, store.latest_confirmed, confirmed)
    ):
        store.latest_confirmed = confirmed
```

#### New `record_block_receipt_time`

```python
def record_block_receipt_time(store: Store, root: Root) -> None:
    """
    Store block receipt time.
    """
    store.block_receipt_times[root] = store.time_ms
```

#### New `record_payload_receipt_time`

```python
def record_payload_receipt_time(store: Store, root: Root) -> None:
    """
    Store payload receipt time.
    """
    store.payload_receipt_times[root] = store.time_ms
```

#### New `record_head_vote_committee`

*Note*: Store the head vote committee for a vote from the previous or current
slot. Other slot committees aren't used in any of AC walks. Assumes all branches
agree on the committee for a given slot.

```python
def record_head_vote_committee(store: Store, state: BeaconState, data: HeadVoteData) -> None:
    """
    Store head vote committee.
    """
    if data.slot + 1 >= get_current_slot(store):
        if data.slot in store.head_vote_committees:
            assert store.head_vote_committees[data.slot] == get_head_vote_committee(
                state, data.slot
            )
        else:
            store.head_vote_committees[data.slot] = get_head_vote_committee(state, data.slot)
```

#### New `record_head_vote_message`

```python
def record_head_vote_message(store: Store, state: BeaconState, message: HeadVoteMessage) -> None:
    """
    Store head vote message in the pool, updates its receipt time and its slot committee.
    """
    # Add message to the pool
    slot_pool = store.head_vote_messages.get(message.data.slot, [])
    slot_pool.append(message)
    store.head_vote_messages[message.data.slot] = slot_pool

    # Add receipt time
    message_root = hash_tree_root(message)
    store.head_vote_message_receipt_times[message_root] = store.time_ms

    # Add committee
    record_head_vote_committee(store, state, message.data)
```

#### New `record_safe_vote`

*Note*: This is the paper's `on_sg_vote`. The pool keeps votes of the rounds in
the expiry window, accepts each vote at most once, and keeps at most two votes
with distinct data per validator per round — the second is equivocation
evidence, and all any rule reads. Active-validator membership is a gossip and
state-transition concern. A refused vote is not consumed: a later delivery may
be admitted after the guard changes.

```python
def record_safe_vote(store: Store, validator_index: ValidatorIndex, data: SafeVoteData) -> None:
    current_round = compute_round_at_slot(get_current_slot(store))
    if data.round > current_round:
        return
    if data.round + SAFE_VOTE_EXPIRY_ROUNDS < current_round:
        return
    if data.round not in store.safe_votes:
        store.safe_votes[data.round] = []
    votes = store.safe_votes[data.round]
    distinct: list[SafeVoteData] = []
    for vote in votes:
        if vote.validator_index != validator_index:
            continue
        if vote.data == data:
            return
        if vote.data not in distinct:
            distinct.append(vote.data)
    if len(distinct) >= 2:
        return
    votes.append(
        StoreSafeVote(validator_index=validator_index, data=data, arrival_ms=store.time_ms)
    )
```

#### New `update_sg_lock`

*Note*: The stabilization layer's lock producer: the active prefix of the saved
grade-1 node joins the lock set beside the fast and slow confirmation locks. The
deadline spans the grade's own round, so a round whose grade does not resolve
lets the lock expire rather than renewing it.

```python
def update_sg_lock(store: Store) -> None:
    fg_frame = get_fg_frame(store)
    prefix = get_active_prefix(store, fg_frame, store.grade_1)
    if prefix is None:
        return
    deadline = (
        compute_time_at_slot_ms(
            store.genesis_time_ms,
            compute_start_slot_at_round(Round(store.grade_1_round + 1)),
        )
        + get_head_vote_due_ms()
    )
    add_lock(store, deadline, prefix)
```

#### New `update_stable_record`

```python
def update_stable_record(store: Store) -> None:
    fg_frame = get_fg_frame(store)
    candidate = get_stable_root(store, fg_frame)
    store.latest_stable = advance_record(store, store.latest_stable, candidate)
```

### `on_tick` helpers

#### New `update_confirmation`

*Notes*: This function:

- Computes a confirmation candidate using all locally known votes for the slot
  and support resolved before the cutoff.
- Saves the candidate even if a live lock vetoes it.
- Without a veto, updates confirmation and creates a lock on the deepest node
  passing either the fast or slow test, if any.
- Clears the fast-confirmed path when no candidate exists or a live lock vetoes
  it.

```python
def update_confirmation(store: Store, slot: Slot) -> None:
    fg_frame = get_fg_frame(store)
    support_cutoff_ms = (
        compute_time_at_slot_ms(store.genesis_time_ms, slot) + get_support_cutoff_ms()
    )
    votes, support_votes = get_combined_local_view(store, slot, INFINITE_TIME_MS, support_cutoff_ms)
    confirmed = get_confirmed_head(store, fg_frame, votes, support_votes, slot)

    # Return if there is no confirmation
    if confirmed is None:
        # Clear the fast confirmed path and return
        store.fast_confirmed_path = set()
        return

    # Return if the confirmation is not compatible with one of the live locks
    if any(
        not is_compatible(store, lock, confirmed)
        for _, lock in get_live_locks(store, fg_frame, store.time_ms)
    ):
        # Save the candidate even when a live lock vetoes it,
        # clear the fast-confirmed path, and return
        store.saved_confirmations[slot] = confirmed
        store.fast_confirmed_path = set()
        return

    fast_confirmed_path, fast_lock = compute_fast_path_and_lock(
        store=store,
        fg_frame=fg_frame,
        votes=votes,
        support_votes=support_votes,
        slot=slot,
        confirmed=confirmed,
    )
    slow_lock = compute_slow_lock(store, fg_frame, slot, confirmed)

    # Write updates to store
    update_locks_and_confirmation(
        store,
        slot,
        fg_frame,
        confirmed,
        fast_confirmed_path,
        fast_lock,
        slow_lock,
    )
```

#### New `unlock`

*Note*: Uses locally resolved votes for `slot` to reconsider locks live at
`time_ms`. If non-equivocating validators holding at least half of all committee
seats support nodes conflicting with a lock, moves it to its deepest ancestor in
the FG frame with opposition below half. The lock's deadline is preserved.

```python
def unlock(store: Store, slot: Slot, time_ms: Uint64) -> None:
    """
    Move opposed live locks to ancestors with opposition below half of all committee seats.
    """
    fg_frame = get_fg_frame(store)
    votes, support_votes = get_combined_local_view(
        store, slot, receipt_threshold_ms=INFINITE_TIME_MS, resolution_threshold_ms=INFINITE_TIME_MS
    )
    equivocating_indices = get_equivocating_indices(votes)

    def is_opposed_by_majority(node: ForkChoiceNode) -> bool:
        # Find non-equivocating validators whose resolved votes support conflicting nodes
        opposing_voters = {
            vote.validator_index
            for vote in support_votes
            if vote.validator_index not in equivocating_indices
            and not is_compatible(store, vote.supported_node, node)
        }
        opposing_score = sum(
            get_validator_seats_count(store, slot, validator_index)
            for validator_index in opposing_voters
        )
        # Opposition must account for at least half of all committee seats
        return 2 * opposing_score >= get_head_vote_committee_seats_count()

    # Consider locks whose deadlines are strictly later than time_ms
    for deadline, lock in get_live_locks(store, fg_frame, time_ms):
        # Only locks in the FG frame with sufficient opposition need a fallback
        if is_opposed_by_majority(lock):
            # Find ancestors in the FG frame opposed by fewer than half of all committee seats
            fallback_path = {
                node
                for node in fg_frame.tree
                if is_ancestor(store, lock, node) and not is_opposed_by_majority(node)
            }
            # Move to the deepest qualifying ancestor, preserving the deadline
            add_lock(store, deadline, get_deepest_node(store, fallback_path))
```

### `on_head_vote_message` helpers

#### New `is_valid_head_vote_message`

```python
def is_valid_head_vote_message(state: BeaconState, message: HeadVoteMessage) -> bool:
    """
    Return ``True`` if head vote message is valid.
    """
    # Vote must have correct payload_status
    if message.data.payload_status not in [
        PAYLOAD_STATUS_EMPTY,
        PAYLOAD_STATUS_FULL,
        PAYLOAD_STATUS_PENDING,
    ]:
        return False

    # Validator must belong to the selected committee
    if message.validator_index not in get_head_vote_committee(state, message.data.slot):
        return False

    # Vote must have a valid signature
    domain = get_domain(state, DOMAIN_HEAD_VOTE, compute_epoch_at_slot(message.data.slot))
    signing_root = compute_signing_root(message.data, domain)
    return bls.Verify(
        state.validators[message.validator_index].pubkey, signing_root, message.signature
    )
```

## Handlers

### Modified `on_tick`

*Note*: Runs an unlocking or confirmation duty if scheduled at `time_ms`, then
updates the store time. Callers must process this tick before other events at
the same timestamp.

```python
def on_tick(store: Store, time_ms: Uint64) -> None:
    time_into_slot_ms = (time_ms - store.genesis_time_ms) % SLOT_DURATION_MS
    slot = compute_slot_at_time_ms(store.genesis_time_ms, time_ms)

    if slot > GENESIS_SLOT and time_into_slot_ms == get_head_vote_due_ms():
        unlock(store, slot - 1, time_ms)

    if slot > GENESIS_SLOT and time_into_slot_ms == get_support_cutoff_ms():
        update_confirmation(store, slot - 1)

    # Update store time
    store.time_ms = time_ms

    # Evaluate the stabilization grades, lock and record due by this tick
    update_grades(store)
    update_sg_lock(store)
    update_stable_record(store)
```

### Modified `on_block`

*Note*: This function is modified to update finality with the new finality
gadget, record block receipt time and store head vote committees.

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.
    """
    block = signed_block.message
    block_root = hash_tree_root(block)

    # Return early if the block is already known
    if block_root in store.blocks:
        return

    # Parent block must be known
    assert block.parent_root in store.block_states

    # If this block builds on the parent's full payload, that payload must
    # have been verified by on_execution_payload_envelope
    if is_parent_node_full(store, block):
        assert is_payload_verified(store, block.parent_root)

    # Blocks cannot be in the future. If they are, their consideration must be delayed until they are in the past.
    current_slot = get_current_slot(store)
    assert current_slot >= block.slot

    # [Modified in EIP8453]
    # Run finalized check over the parent to avoid circular dependency.
    assert is_ancestor_root(store, block.parent_root, store.finalized_checkpoint.root)

    # Make a copy of the state to avoid mutability issues
    state = store.block_states[block.parent_root].copy()

    # Check the block is valid and compute the post-state
    state_transition(state, signed_block, validate_result=True)

    # Add new block to the store
    store.blocks[block_root] = block
    # Add new state for this block to the store
    store.block_states[block_root] = state
    # Add a new PTC voting for this block to the store
    store.payload_timeliness_vote[block_root] = [None] * PTC_SIZE
    store.payload_data_availability_vote[block_root] = [None] * PTC_SIZE

    # [Modified in EIP8453]
    update_finality(store, state)

    # [New in EIP8453]
    # Record block receipt time
    record_block_receipt_time(store, block_root)

    # [New in EIP8453]
    for vote in block.body.head_votes:
        record_head_vote_committee(store, state, vote.data)

    # Record the safe votes the block carries
    for safe_vote in block.body.safe_votes:
        for validator_index in safe_vote.voter_indices:
            record_safe_vote(store, validator_index, safe_vote.data)

    # Notify the store about the payload_attestations in the block
    notify_ptc_messages(store, state, block.body.payload_attestations)
```

### Modified `on_execution_payload_envelope`

*Note*: This function is modified to record payload receipt time.

```python
def on_execution_payload_envelope(
    store: Store, signed_envelope: SignedExecutionPayloadEnvelope
) -> None:
    """
    Run ``on_execution_payload_envelope`` upon receiving a new execution payload envelope.
    """
    envelope = signed_envelope.message

    # Return early if the payload is already known
    if is_payload_verified(store, envelope.beacon_block_root):
        return

    # The corresponding beacon block root needs to be known
    assert envelope.beacon_block_root in store.block_states

    # Check if blob data is available
    # If not, this payload MAY be queued and subsequently considered when blob data becomes available
    assert is_data_available(envelope.beacon_block_root)

    state = store.block_states[envelope.beacon_block_root]

    # Verify the execution payload envelope
    verify_execution_payload_envelope(state, signed_envelope, EXECUTION_ENGINE)

    # Check if this payload satisfies the inclusion list constraints
    # If not, add this payload to the store as inclusion list constraints unsatisfied
    record_payload_inclusion_list_satisfaction(
        store, envelope.beacon_block_root, envelope.payload, EXECUTION_ENGINE
    )

    # [New in EIP8453]
    # Record payload receipt time
    record_payload_receipt_time(store, envelope.beacon_block_root)

    # Add execution payload envelope to the store
    store.payloads[envelope.beacon_block_root] = envelope
```

### New `on_head_vote_message`

*Note*: Validates and stores head vote P2P message.

```python
def on_head_vote_message(store: Store, message: HeadVoteMessage) -> None:
    current_slot = get_current_slot(store)
    previous_slot = saturating_sub(current_slot, 1)

    # Message must not have been seen
    assert message not in store.head_vote_messages.get(message.data.slot, [])

    # Vote must be from the previous or current slot.
    # Delay consideration in the fork-choice until their slot is in the past.
    assert message.data.slot in [previous_slot, current_slot]

    # Use pulled up head state
    state = get_pulled_up_state(store, get_head(store).root)
    assert is_valid_head_vote_message(state, message)

    # Record the message
    record_head_vote_message(store, state, message)
```

### New `on_safe_vote`

*Note*: Run upon receiving a `SafeVoteMessage` on the wire, or upon decomposing
a `SafeVote` aggregate into its voters. Signature and membership verification
are gossip concerns, specified in the networking guide; the state transition
re-verifies the votes a block carries.

```python
def on_safe_vote(store: Store, message: SafeVoteMessage) -> None:
    data = message.data
    assert data.payload_status in (
        PAYLOAD_STATUS_EMPTY,
        PAYLOAD_STATUS_FULL,
        PAYLOAD_STATUS_PENDING,
    )
    record_safe_vote(store, message.validator_index, data)
```

## Internal API

### New `get_ac_proposal`

*Note*: At the start of a slot, selects the proposal head using received and
resolved P2P votes from the previous slot. Returns the head, vote messages, and
supporting message indices.

```python
def get_ac_proposal(
    store: Store,
) -> tuple[ForkChoiceNode, list[HeadVoteMessage], list[int]]:
    assert get_time_into_slot_ms(store) == Uint64(0)

    current_slot = get_current_slot(store)
    assert current_slot > GENESIS_SLOT

    fg_frame = get_fg_frame(store)
    vote_messages, support_indices = get_local_view_from_p2p_messages(
        store,
        current_slot - 1,
        receipt_threshold_ms=INFINITE_TIME_MS,
        resolution_threshold_ms=INFINITE_TIME_MS,
    )

    # Build the view from P2P messages only
    votes, support_votes = compute_merged_view((vote_messages, support_indices), ([], []))
    head = get_head_in_tree(
        store=store,
        fg_frame=fg_frame,
        tree=fg_frame.tree,
        votes=votes,
        support_votes=support_votes,
        slot=current_slot - 1,
    )

    # Convert a pending head to empty for proposal construction
    if head.payload_status == PAYLOAD_STATUS_PENDING:
        head = ForkChoiceNode(root=head.root, payload_status=PAYLOAD_STATUS_EMPTY)

    return head, vote_messages, support_indices
```

### New `get_ac_vote_head`

*Note*: Selects the head for an AC vote at the head vote deadline. Merges the
frozen local P2P view with views from current slot proposals, then walks the
voter's viable subtree.

```python
def get_ac_vote_head(store: Store) -> ForkChoiceNode:
    assert get_time_into_slot_ms(store) == get_head_vote_due_ms()

    current_slot = get_current_slot(store)
    if current_slot == GENESIS_SLOT:
        return ForkChoiceNode(
            root=store.finalized_checkpoint.root,
            payload_status=PAYLOAD_STATUS_EMPTY,
        )

    fg_frame = get_fg_frame(store)
    view_freeze_ms = (
        compute_time_at_slot_ms(store.genesis_time_ms, current_slot - 1) + get_view_freeze_ms()
    )
    # Local view
    local_view = get_local_view_from_p2p_messages(
        store,
        current_slot - 1,
        receipt_threshold_ms=view_freeze_ms,
        resolution_threshold_ms=view_freeze_ms,
    )
    # Proposer view
    proposer_view = get_proposer_view(store, current_slot, current_slot - 1)
    # Merge views
    votes, support_votes = compute_merged_view(local_view, proposer_view)

    # Run over voter viable subtree
    voter_subtree = get_voter_subtree(store, fg_frame.tree, current_slot)
    head = get_head_in_tree(
        store=store,
        fg_frame=fg_frame,
        tree=voter_subtree,
        votes=votes,
        support_votes=support_votes,
        slot=current_slot - 1,
    )

    # Never return pending nodes for previous slots
    if (
        store.blocks[head.root].slot < current_slot
        and head.payload_status == PAYLOAD_STATUS_PENDING
    ):
        return ForkChoiceNode(root=head.root, payload_status=PAYLOAD_STATUS_EMPTY)
    else:
        return head
```

### New `get_ac_frame`

*Notes*: At or after the support cutoff, returns the FG confirmation node and
the head selected using the current slot's local vote view.

The FG confirmation node is the deepest node in both the fast-confirmed path and
the full viable subtree, or `None` if no such node exists.

The AC frame is used by validators to cast FG attestations.

```python
def get_ac_frame(store: Store) -> tuple[ForkChoiceNode | None, ForkChoiceNode]:
    assert get_time_into_slot_ms(store) >= get_support_cutoff_ms()

    current_slot = get_current_slot(store)
    fg_frame = get_fg_frame(store)
    votes, support_votes = get_combined_local_view(
        store,
        current_slot,
        receipt_threshold_ms=INFINITE_TIME_MS,
        resolution_threshold_ms=INFINITE_TIME_MS,
    )
    head = get_head_in_tree(
        store=store,
        fg_frame=fg_frame,
        tree=fg_frame.tree,
        votes=votes,
        support_votes=support_votes,
        slot=current_slot,
    )

    # The deepest viable node from the fast confirmed path
    viable_subtree = get_viable_subtree(store, fg_frame, fg_frame.tree)
    fast_confirmed_viable_nodes = store.fast_confirmed_path & set(viable_subtree)
    if len(fast_confirmed_viable_nodes) > 0:
        fg_confirmed = get_deepest_node(store, fast_confirmed_viable_nodes)
        return fg_confirmed, head
    else:
        return None, head
```

### FG attestation sources

The FG reads two things back from the available chain. The *target source* is
the confirmed node: a target vote can create a justification, and only confirmed
blocks may be justified. The *finality source* is the head: its subject is
already justified, so it may read an unconfirmed chain, and the head chain state
holds the freshest justification. The validator guide builds `AttestationData`
from these two states together with the validator's signing record; the record
itself belongs to the validator client and is out of scope here.

#### New `get_fg_target_source`

```python
def get_fg_target_source(store: Store) -> BeaconState:
    return store.block_states[get_confirmed_node(store).root]
```

#### New `get_fg_finality_source`

```python
def get_fg_finality_source(store: Store) -> BeaconState:
    head = get_head(store)
    return store.block_states[head.root]
```

#### New `has_fresh_safe_quorum`

*Note*: A validator emits a height pair only in rounds whose grade-2 node is
compatible with the forkchoice root — fresh quorum evidence from the
stabilization layer. Without it, the attestation carries its finality pair
alone. The test is compatibility, not an active prefix: heights advance per
block while grades resolve per round, so on a healthy chain the grade trails the
justified root as its ancestor. Requiring the grade to descend the forkchoice
root would withhold height pairs until a timeout lowered the root back to the
finalized checkpoint, degrading justification to an oscillation at timeout
speed.

```python
def has_fresh_safe_quorum(store: Store) -> bool:
    grade = store.grade_2
    if grade is None or grade.root not in store.blocks:
        return False
    fg_root = get_fg_frame(store).forkchoice_root
    return is_compatible(store, grade, fg_root)
```

### New `get_confirmed_execution_block_hash`

*Note*: Returns the confirmed execution block hash for the Engine API. In the
case of an empty slot a payload from a past slot can still be confirmed.

```python
def get_confirmed_execution_block_hash(store: Store) -> Hash32:
    confirmed_node = get_confirmed_node(store)
    confirmed_block = store.blocks[confirmed_node.root]
    bid = confirmed_block.body.signed_execution_payload_bid.message
    if confirmed_node.payload_status == PAYLOAD_STATUS_FULL:
        return bid.block_hash
    else:
        return bid.parent_block_hash
```

## External API

### New `get_confirmed_node`

*Note*: Returns the latest confirmed node, falling back to the finalized node if
it is outside the subtree rooted at finalized block or conflicts with the
current head.

```python
def get_confirmed_node(store: Store) -> ForkChoiceNode:
    fg_frame = get_fg_frame(store)

    # Fallback to finality if the latest confirmed is out of the FG frame
    if (
        store.latest_confirmed not in fg_frame.tree
        or store.latest_confirmed == fg_frame.finalized_node
    ):
        return fg_frame.finalized_node

    # Fall back to finality if the latest confirmed node conflicts with the current head
    head = get_head(store)
    if not is_compatible(store, head, store.latest_confirmed):
        return fg_frame.finalized_node

    return store.latest_confirmed
```

### Modified `get_head`

*Note*: This function is modified to use the new fork-choice algorithm. It uses
current slot votes at or after the support cutoff, and previous slot votes
otherwise.

```python
def get_head(store: Store) -> ForkChoiceNode:
    current_slot = get_current_slot(store)
    if current_slot == GENESIS_SLOT:
        return ForkChoiceNode(
            root=store.finalized_checkpoint.root,
            payload_status=PAYLOAD_STATUS_EMPTY,
        )

    if get_time_into_slot_ms(store) >= get_support_cutoff_ms():
        slot = current_slot
    else:
        slot = current_slot - 1

    fg_frame = get_fg_frame(store)
    votes, support_votes = get_combined_local_view(
        store, slot, receipt_threshold_ms=INFINITE_TIME_MS, resolution_threshold_ms=INFINITE_TIME_MS
    )
    head = get_head_in_tree(
        store=store,
        fg_frame=fg_frame,
        tree=fg_frame.tree,
        votes=votes,
        support_votes=support_votes,
        slot=slot,
    )

    # Never return pending
    if head.payload_status == PAYLOAD_STATUS_PENDING:
        return ForkChoiceNode(root=head.root, payload_status=PAYLOAD_STATUS_EMPTY)
    else:
        return head
```
