# EIP-8453 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

*Note*: This is a derived first draft. It transcribes the complete protocol of
the decoupled consensus paper (§7, as extracted for the Lean formalization in
`verified-consensus/docs/PROTOCOL.md`) onto the containers and state transition
of the [EIP-8453 beacon chain](./beacon-chain.md), on top of the node-based fork
choice of [Gloas](../../gloas/fork-choice.md) and
[Heze](../../heze/fork-choice.md). Divergences from the paper are collected in
[Divergences from the paper](#divergences-from-the-paper).

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [Modified `notify_forkchoice_updated`](#modified-notify_forkchoice_updated)
- [Types](#types)
  - [New `StoreHeadVote`](#new-storeheadvote)
  - [New `StoreSafeVote`](#new-storesafevote)
- [Helpers](#helpers)
  - [Modified `Store`](#modified-store)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
  - [Time](#time)
    - [New `get_head_vote_due_ms`](#new-get_head_vote_due_ms)
    - [New `get_head_vote_support_due_ms`](#new-get_head_vote_support_due_ms)
    - [New `get_view_freeze_due_ms`](#new-get_view_freeze_due_ms)
  - [Head votes](#head-votes)
    - [New `get_head_vote_committee_at_slot`](#new-get_head_vote_committee_at_slot)
    - [New `get_seat_count`](#new-get_seat_count)
    - [New `get_slot_head_votes`](#new-get_slot_head_votes)
    - [New `get_resolution_time_ms`](#new-get_resolution_time_ms)
    - [New `get_equivocating_voters`](#new-get_equivocating_voters)
    - [New `get_participating_seats`](#new-get_participating_seats)
  - [Goldfish score and walk](#goldfish-score-and-walk)
    - [New `get_goldfish_weight`](#new-get_goldfish_weight)
    - [New `is_goldfish_eligible`](#new-is_goldfish_eligible)
    - [New `compute_goldfish_head`](#new-compute_goldfish_head)
  - [Payload status](#payload-status)
    - [Modified `should_extend_payload`](#modified-should_extend_payload)
    - [New `get_node_execution_block_hash`](#new-get_node_execution_block_hash)
    - [New `get_safe_execution_block_hash`](#new-get_safe_execution_block_hash)
  - [FG restrictions](#fg-restrictions)
    - [New `is_ancestor_root`](#new-is_ancestor_root)
    - [New `get_fg_root`](#new-get_fg_root)
    - [New `get_filtered_roots_from`](#new-get_filtered_roots_from)
    - [New `get_filtered_roots`](#new-get_filtered_roots)
    - [New `is_viable_root`](#new-is_viable_root)
  - [Stabilization](#stabilization)
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
    - [New `clip_node_to_finalized`](#new-clip_node_to_finalized)
    - [New `get_sg_root`](#new-get_sg_root)
    - [New `is_grade_0_compatible`](#new-is_grade_0_compatible)
    - [New `get_stable_root`](#new-get_stable_root)
    - [New `get_safe_vote_node`](#new-get_safe_vote_node)
  - [Head selection](#head-selection)
    - [Modified `get_head`](#modified-get_head)
    - [New `get_voter_head`](#new-get_voter_head)
    - [New `has_head_vote`](#new-has_head_vote)
  - [Confirmation](#confirmation)
    - [New `update_confirmation`](#new-update_confirmation)
    - [New `advance_record`](#new-advance_record)
    - [New `update_confirmation_records`](#new-update_confirmation_records)
    - [New `get_stable`](#new-get_stable)
    - [New `get_confirmed`](#new-get_confirmed)
  - [FG summary](#fg-summary)
    - [New `update_finality`](#new-update_finality)
  - [FG attestation sources](#fg-attestation-sources)
    - [New `get_fg_target_source`](#new-get_fg_target_source)
    - [New `get_fg_finality_source`](#new-get_fg_finality_source)
    - [New `has_fresh_safe_quorum`](#new-has_fresh_safe_quorum)
- [Handlers](#handlers)
  - [Modified `on_tick`](#modified-on_tick)
  - [Modified `on_block`](#modified-on_block)
  - [New `record_head_vote`](#new-record_head_vote)
  - [New `on_head_vote`](#new-on_head_vote)
  - [New `record_safe_vote`](#new-record_safe_vote)
  - [New `on_safe_vote`](#new-on_safe_vote)
- [Divergences from the paper](#divergences-from-the-paper)

<!-- mdformat-toc end -->

## Introduction

This document replaces LMD-GHOST with the fork choice of EIP-8453. Head
selection is a one-slot GHOST walk over the previous slot's head votes, cast by
the slot's head vote committee. The finality gadget constrains the walk only
through a narrow interface: the walk starts at the FG root and is confined to
viable branches. These are the *FG restrictions*.

FG attestations play no part in the fork choice. Their effect arrives
exclusively through the blocks that include them: processing a block runs the
state transition, and the post-state's height, justification and finalization
summaries are folded into the store by `update_finality`. There is no
`on_attestation` handler, no latest-message tracking, and no attestation weight
accumulation. The store processes only time, blocks, head votes, and safe votes.

Because a head vote only carries weight for one slot, withheld votes cannot
accumulate, and the view-merge mechanism replaces proposer boost: the proposer
of a slot publishes the previous slot's votes inside its block, and voters
reconcile with that published view before voting.

Across rounds, stabilization comes from the safe votes: once per round, every
active validator names the node it considers confirmed, and near each round
boundary the store takes the *relative majority* of the recent safe votes —
supporters of a node against the validators that moved away from it — at three
staggered cutoff pairs, saving the deepest node passing each test as the round's
three *grades*. The grade-1 node anchors every head walk, the grade-0 node
vetoes conflicting safe votes, and the grade-2 node backs the stable record. The
cutoffs are spaced one quarter-slot apart, so under synchrony a node holding
grade 2 anywhere holds grade 1 everywhere, and grade 1 anywhere holds grade 0
everywhere: this *graded delivery* is what carries one node's stabilization to
every other honest node.

The fork choice exposes four nested tips: the finalized block, the stable block
(`get_stable`), the confirmed block (`get_confirmed`), and the head
(`get_head`), with `finalized ⪯ stable ⪯ confirmed ⪯ head` under the protocol's
assumptions.

*Note*: This specification is built upon [Heze](../../heze/fork-choice.md).

## Constants

The slot schedule of the paper divides the slot into quarters, `Δ = slot / 4`:
the proposal at `t_s`, head voting at `t_s + Δ`, the support cutoff at
`t_s + 2Δ`, and the view freeze at `t_s + 3Δ`. The confirmation of slot `s` is
evaluated at `t_s + 6Δ`, which is the support cutoff of slot `s + 1`.

| Name                        | Value          |
| --------------------------- | -------------- |
| `HEAD_VOTE_DUE_BPS`         | `Uint64(2500)` |
| `HEAD_VOTE_SUPPORT_DUE_BPS` | `Uint64(5000)` |
| `VIEW_FREEZE_DUE_BPS`       | `Uint64(7500)` |

The grades of round `r` are evaluated at three cutoff pairs anchored to the
round's start time `T_r`, each an early cutoff fixing the supporters and a late
cutoff admitting counter-evidence, and each pair one `Δ` from the next:

| Grade | Early cutoff | Late cutoff | Complete at |
| ----- | ------------ | ----------- | ----------- |
| 2     | `T_r − 5Δ`   | `T_r − Δ`   | `T_r − Δ`   |
| 1     | `T_r − 4Δ`   | `T_r − 2Δ`  | `T_r`       |
| 0     | `T_r − 3Δ`   | `T_r − 3Δ`  | `T_r + Δ`   |

## Protocols

### `ExecutionEngine`

#### Modified `notify_forkchoice_updated`

In EIP-8453, the forkchoice state values **MUST** be computed as follows. All
other semantics of `notify_forkchoice_updated` and its invocation are inherited
from prior upgrades. The fast confirmation rule of prior upgrades is deprecated;
the confirmed tip takes its place as the safe block.

- `head_block_hash = get_node_execution_block_hash(store, get_head(store))`
- `safe_block_hash = get_safe_execution_block_hash(store)`
- `finalized_block_hash = finalized_block_bid.parent_block_hash`

Where:

- `finalized_block = store.blocks[store.finalized_checkpoint.root]`
- `finalized_block_bid = finalized_block.body.signed_execution_payload_bid.message`

## Types

### New `StoreHeadVote`

*Note*: A head vote as the store keeps it: one voter, the signed data, and the
time at which the store processed it. Aggregates decompose into these entries.
The arrival time stands in for the paper's `Σ.timestamp[·]`.

```python
@dataclass(eq=True, frozen=True)
class StoreHeadVote:
    validator_index: ValidatorIndex
    data: HeadVoteData
    arrival_ms: Uint64
```

### New `StoreSafeVote`

```python
@dataclass(eq=True, frozen=True)
class StoreSafeVote:
    validator_index: ValidatorIndex
    data: SafeVoteData
    arrival_ms: Uint64
```

## Helpers

### Modified `Store`

*Note*: The Casper FFG checkpoints, the latest messages, the unrealized
justification machinery, the proposer boost and the equivocation set are
removed. In their place the store keeps the FG summary of the paper's store Σ —
the finalized checkpoint `F`, the lex-greatest compatible justification `J`, and
the maximum height `h_max` — together with the head vote pools, block arrival
times, and the confirmation records. `confirmed` is the protocol-facing
`Σ.live_confirmed`: only this value is read by the voting rules.
`latest_confirmed` is the user-facing record. `confirmation_slot` is the highest
slot whose confirmation has been evaluated.

```python
@dataclass
class Store:
    time_ms: Uint64
    genesis_time_ms: Uint64
    # [Modified in EIP8453]
    justified_checkpoint: HeightCheckpoint
    # [Modified in EIP8453]
    finalized_checkpoint: HeightCheckpoint
    # [New in EIP8453]
    finalized_slot: Slot
    # [New in EIP8453]
    max_height: Height
    blocks: dict[Root, BeaconBlock]
    block_states: dict[Root, BeaconState]
    block_timeliness: dict[Root, list[bool]]
    # [New in EIP8453]
    block_arrivals_ms: dict[Root, Uint64]
    # [New in EIP8453]
    head_votes: dict[Slot, list[StoreHeadVote]]
    # [New in EIP8453]
    safe_votes: dict[Round, list[StoreSafeVote]]
    # [New in EIP8453]
    grade_2: ForkChoiceNode | None
    # [New in EIP8453]
    grade_1: ForkChoiceNode | None
    # [New in EIP8453]
    grade_0: ForkChoiceNode | None
    # [New in EIP8453]
    grade_2_round: Round
    # [New in EIP8453]
    grade_1_round: Round
    # [New in EIP8453]
    grade_0_round: Round
    # [New in EIP8453]
    confirmed: ForkChoiceNode
    # [New in EIP8453]
    latest_confirmed: ForkChoiceNode
    # [New in EIP8453]
    latest_stable: ForkChoiceNode
    # [New in EIP8453]
    confirmation_slot: Slot
    payloads: dict[Root, ExecutionPayloadEnvelope]
    payload_timeliness_vote: dict[Root, list[Boolean | None]]
    payload_data_availability_vote: dict[Root, list[Boolean | None]]
    payload_inclusion_list_satisfaction: dict[Root, bool]
    # [Modified in EIP8453]
    # Removed `unrealized_justified_checkpoint`
    # [Modified in EIP8453]
    # Removed `unrealized_finalized_checkpoint`
    # [Modified in EIP8453]
    # Removed `proposer_boost_root`
    # [Modified in EIP8453]
    # Removed `equivocating_indices`
    # [Modified in EIP8453]
    # Removed `checkpoint_states`
    # [Modified in EIP8453]
    # Removed `latest_messages`
    # [Modified in EIP8453]
    # Removed `unrealized_justifications`
```

### Modified `get_forkchoice_store`

*Note*: As in prior forks, the anchor stands in for both the justified and the
finalized root, whatever roots the anchor state itself records.

```python
def get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock) -> Store:
    assert anchor_block.state_root == hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block)
    anchor_node = ForkChoiceNode(root=anchor_root, payload_status=PAYLOAD_STATUS_PENDING)
    justified_checkpoint = HeightCheckpoint(
        height=anchor_state.justified_checkpoint.height, root=anchor_root
    )
    finalized_checkpoint = HeightCheckpoint(
        height=anchor_state.finalized_checkpoint.height, root=anchor_root
    )
    genesis_time_ms = seconds_to_milliseconds(anchor_state.genesis_time)
    time_ms = compute_time_at_slot_ms(genesis_time_ms, anchor_state.slot)
    return Store(
        time_ms=time_ms,
        genesis_time_ms=genesis_time_ms,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        finalized_slot=anchor_state.finalized_slot,
        max_height=anchor_state.target_checkpoint.height,
        blocks={anchor_root: anchor_block.copy()},
        block_states={anchor_root: anchor_state.copy()},
        block_timeliness={anchor_root: [True, True]},
        block_arrivals_ms={anchor_root: time_ms},
        head_votes={},
        safe_votes={},
        grade_2=None,
        grade_1=None,
        grade_0=None,
        grade_2_round=compute_round_at_slot(anchor_state.slot),
        grade_1_round=compute_round_at_slot(anchor_state.slot),
        grade_0_round=compute_round_at_slot(anchor_state.slot),
        confirmed=anchor_node,
        latest_confirmed=anchor_node,
        latest_stable=anchor_node,
        confirmation_slot=anchor_state.slot,
        payloads={},
        payload_timeliness_vote={anchor_root: [None] * PTC_SIZE},
        payload_data_availability_vote={anchor_root: [None] * PTC_SIZE},
        payload_inclusion_list_satisfaction={},
    )
```

### Time

#### New `get_head_vote_due_ms`

```python
def get_head_vote_due_ms() -> Uint64:
    return get_slot_component_duration_ms(HEAD_VOTE_DUE_BPS)
```

#### New `get_head_vote_support_due_ms`

```python
def get_head_vote_support_due_ms() -> Uint64:
    return get_slot_component_duration_ms(HEAD_VOTE_SUPPORT_DUE_BPS)
```

#### New `get_view_freeze_due_ms`

```python
def get_view_freeze_due_ms() -> Uint64:
    return get_slot_component_duration_ms(VIEW_FREEZE_DUE_BPS)
```

### Head votes

#### New `get_head_vote_committee_at_slot`

*Note*: The dependent state for committee computation is the latest finalized
block's post-state: it is stable across branches, every head vote's committee
descends from it, and it changes only on finality advances, when assignments are
recomputed. The same choice fixes the weight-reading state of the stabilization
rule.

```python
def get_head_vote_committee_at_slot(store: Store, slot: Slot) -> HeadVoteCommittee:
    state = store.block_states[store.finalized_checkpoint.root]
    epoch = compute_epoch_at_slot(slot)
    if compute_epoch_at_slot(state.slot) + MIN_SEED_LOOKAHEAD < epoch:
        state = state.copy()
        process_slots(state, compute_start_slot_at_epoch(Epoch(epoch - MIN_SEED_LOOKAHEAD)))
    return get_head_vote_committee(state, slot)
```

#### New `get_seat_count`

*Note*: The committee is sampled by effective balance and may hold the same
validator in several seats. A validator's vote counts once per seat, so all
scores below are in seats, not validators.

```python
def get_seat_count(committee: HeadVoteCommittee, validator_index: ValidatorIndex) -> Uint64:
    seats = Uint64(0)
    for index in committee:
        if index == validator_index:
            seats += 1
    return seats
```

#### New `get_slot_head_votes`

```python
def get_slot_head_votes(store: Store, slot: Slot) -> Sequence[StoreHeadVote]:
    if slot in store.head_votes:
        return store.head_votes[slot]
    return []
```

#### New `get_resolution_time_ms`

*Note*: A head vote *resolves* when the store holds its head and the head is a
block of the vote's slot or earlier. A vote whose head is a later-slot block
stays in the pool as a cast vote but never resolves, so it is never counted as
support for its head. This is the paper's `Σ.resolution_time`, with `None` for
the paper's `+∞`.

```python
def get_resolution_time_ms(store: Store, vote: StoreHeadVote) -> Uint64 | None:
    root = vote.data.beacon_block_root
    if root not in store.blocks:
        return None
    if store.blocks[root].slot > vote.data.slot:
        return None
    return max(vote.arrival_ms, store.block_arrivals_ms[root])
```

#### New `get_equivocating_voters`

*Note*: A validator equivocates when the vote set holds two of its distinct
votes. The pool admits at most two distinct votes per validator per slot, which
is all this rule reads.

```python
def get_equivocating_voters(votes: Sequence[StoreHeadVote]) -> set[ValidatorIndex]:
    first_votes: dict[ValidatorIndex, HeadVoteData] = {}
    equivocating: set[ValidatorIndex] = set()
    for vote in votes:
        if vote.validator_index in first_votes:
            if first_votes[vote.validator_index] != vote.data:
                equivocating.add(vote.validator_index)
        else:
            first_votes[vote.validator_index] = vote.data
    return equivocating
```

#### New `get_participating_seats`

```python
def get_participating_seats(committee: HeadVoteCommittee, votes: Sequence[StoreHeadVote]) -> Uint64:
    voters: set[ValidatorIndex] = set()
    for vote in votes:
        voters.add(vote.validator_index)
    seats = Uint64(0)
    for voter in voters:
        seats += get_seat_count(committee, voter)
    return seats
```

### Goldfish score and walk

#### New `get_goldfish_weight`

*Note*: This is the paper's `goldfish_score`, in seats. Every equivocator counts
for every node and stays among the participants: discovering an equivocation
cannot make a majority-eligible node ineligible, though it can make another node
newly eligible. A non-equivocating validator counts once, in one subtree,
through its vote in `support_votes`.

```python
def get_goldfish_weight(
    store: Store,
    committee: HeadVoteCommittee,
    votes: Sequence[StoreHeadVote],
    support_votes: Sequence[StoreHeadVote],
    node: ForkChoiceNode,
) -> Uint64:
    equivocating = get_equivocating_voters(votes)
    supporting: set[ValidatorIndex] = set()
    for vote in support_votes:
        if vote.validator_index in equivocating:
            continue
        if vote.data.beacon_block_root not in store.blocks:
            continue
        vote_node = ForkChoiceNode(
            root=vote.data.beacon_block_root,
            payload_status=vote.data.payload_status,
        )
        if is_ancestor(store, vote_node, node):
            supporting.add(vote.validator_index)
    weight = Uint64(0)
    for voter in equivocating:
        weight += get_seat_count(committee, voter)
    for voter in supporting:
        weight += get_seat_count(committee, voter)
    return weight
```

#### New `is_goldfish_eligible`

*Note*: This is the paper's `goldfish_eligible`. A node is eligible when its
subtree holds a strict majority of the participating seats, when its block is a
proposal of the current slot, which cannot yet have votes, or — unless
`majority_only` — when its parent's state height is below the viability band,
where the majority gate does not apply. The confirmation walk passes
`majority_only=True`, since only a genuine majority may confirm.

```python
def is_goldfish_eligible(
    store: Store,
    committee: HeadVoteCommittee,
    votes: Sequence[StoreHeadVote],
    support_votes: Sequence[StoreHeadVote],
    node: ForkChoiceNode,
    majority_only: bool,
) -> bool:
    block = store.blocks[node.root]
    if not majority_only:
        if block.slot == get_current_slot(store):
            return True
        if block.parent_root in store.block_states:
            parent_height = store.block_states[block.parent_root].target_checkpoint.height
            if parent_height + 1 < store.max_height:
                return True
    weight = get_goldfish_weight(store, committee, votes, support_votes, node)
    return 2 * weight > get_participating_seats(committee, votes)
```

#### New `compute_goldfish_head`

*Note*: This is the paper's `ghost` walk. It descends from the anchor through
eligible children within the view, taking the highest seat score at each step,
and stops where no child is eligible. The walk starts at the anchor even when
the anchor itself is outside the view.

```python
def compute_goldfish_head(
    store: Store,
    anchor: ForkChoiceNode,
    view: set[Root],
    committee: HeadVoteCommittee,
    votes: Sequence[StoreHeadVote],
    support_votes: Sequence[StoreHeadVote],
    majority_only: bool,
) -> ForkChoiceNode:
    head = anchor
    while True:
        children = [
            child
            for child in get_node_children(store, head)
            if child.root in view
            and is_goldfish_eligible(store, committee, votes, support_votes, child, majority_only)
        ]
        if len(children) == 0:
            return head
        head = max(
            children,
            key=lambda child: (
                get_goldfish_weight(store, committee, votes, support_votes, child),
                child.root,
                get_payload_status_tiebreaker(store, child),
            ),
        )
```

### Payload status

#### Modified `should_extend_payload`

*Note*: With proposer boost removed, the escape clauses that read the boosted
proposer's choice are removed with it: a previous-slot payload is extended only
when it is verified, satisfies the inclusion list constraints, and the PTC saw
it as timely and available.

```python
def should_extend_payload(store: Store, root: Root) -> bool:
    assert store.blocks[root].slot + 1 == get_current_slot(store)
    if not is_payload_verified(store, root):
        return False
    if not is_payload_inclusion_list_satisfied(store, root):
        return False
    payload_is_timely = payload_timeliness(store, root, timely=True)
    payload_data_is_available = payload_data_availability(store, root, available=True)
    return payload_is_timely and payload_data_is_available
```

#### New `get_node_execution_block_hash`

*Note*: The execution block hash a fork-choice node stands for: the node's own
payload when it is *full*, and the parent chain's latest payload when the node's
payload is *empty* or still *pending*.

```python
def get_node_execution_block_hash(store: Store, node: ForkChoiceNode) -> Hash32:
    bid = store.blocks[node.root].body.signed_execution_payload_bid.message
    if node.payload_status == PAYLOAD_STATUS_FULL:
        return bid.block_hash
    return bid.parent_block_hash
```

#### New `get_safe_execution_block_hash`

*Note*: The engine requires the safe block to be an ancestor of the head. The
confirmed record can transiently leave the head's chain in unsafe periods, so
the safe hash falls back to the finalized block — which descends from no walk
anchor and is an ancestor of every head by construction — whenever the confirmed
node does not precede the head.

```python
def get_safe_execution_block_hash(store: Store) -> Hash32:
    head = get_head(store)
    confirmed = get_confirmed(store)
    if confirmed == head or is_ancestor(store, head, confirmed):
        return get_node_execution_block_hash(store, confirmed)
    finalized = ForkChoiceNode(
        root=store.finalized_checkpoint.root, payload_status=PAYLOAD_STATUS_PENDING
    )
    return get_node_execution_block_hash(store, finalized)
```

### FG restrictions

#### New `is_ancestor_root`

```python
def is_ancestor_root(store: Store, ancestor_root: Root, descendant_root: Root) -> bool:
    ancestor = ForkChoiceNode(root=ancestor_root, payload_status=PAYLOAD_STATUS_PENDING)
    descendant = ForkChoiceNode(root=descendant_root, payload_status=PAYLOAD_STATUS_PENDING)
    return is_ancestor(store, descendant, ancestor)
```

#### New `get_fg_root`

*Note*: The FG root is the justified checkpoint while the chain is at the
justification's own height band, and the finalized checkpoint otherwise. The
head walk may never leave its subtree. This is the narrow interface by which the
finality gadget constrains the available chain.

```python
def get_fg_root(store: Store) -> Root:
    if store.max_height == store.justified_checkpoint.height + 1:
        return store.justified_checkpoint.root
    return store.finalized_checkpoint.root
```

#### New `get_filtered_roots_from`

*Note*: This is the paper's `get_filtered_block_tree_from`: the blocks of the
view that descend the FG root and are *viable*, that is, have a descendant in
the view whose state height is at most one below the maximum seen.

```python
def get_filtered_roots_from(store: Store, roots: set[Root]) -> set[Root]:
    fg_root = get_fg_root(store)
    candidates = [root for root in roots if is_ancestor_root(store, fg_root, root)]
    tips = [
        root
        for root in candidates
        if store.block_states[root].target_checkpoint.height + 1 >= store.max_height
    ]
    filtered: set[Root] = set()
    for root in candidates:
        for tip in tips:
            if is_ancestor_root(store, root, tip):
                filtered.add(root)
                break
    return filtered
```

#### New `get_filtered_roots`

```python
def get_filtered_roots(store: Store) -> set[Root]:
    return get_filtered_roots_from(store, set(store.blocks.keys()))
```

#### New `is_viable_root`

```python
def is_viable_root(store: Store, root: Root) -> bool:
    for tip in store.blocks:
        if not is_ancestor_root(store, root, tip):
            continue
        if store.block_states[tip].target_checkpoint.height + 1 >= store.max_height:
            return True
    return False
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
    return max(vote.arrival_ms, store.block_arrivals_ms[root])
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

*Note*: A saved grade is *active* when it has an ancestor in the filtered tree,
and its active prefix is the deepest such ancestor: the fork choice can use it,
and it descends the FG root.

```python
def get_active_prefix(store: Store, node: ForkChoiceNode | None) -> ForkChoiceNode | None:
    if node is None or node.root not in store.blocks:
        return None
    filtered = get_filtered_roots(store)
    current: ForkChoiceNode | None = node
    while current is not None:
        if current.root in filtered:
            return current
        current = get_node_parent(store, current)
    return None
```

#### New `clip_node_to_finalized`

```python
def clip_node_to_finalized(store: Store, node: ForkChoiceNode | None) -> ForkChoiceNode | None:
    if node is None or node.root not in store.blocks:
        return None
    finalized_root = store.finalized_checkpoint.root
    current: ForkChoiceNode | None = node
    while current is not None:
        is_compatible = is_ancestor_root(store, finalized_root, current.root) or is_ancestor_root(
            store, current.root, finalized_root
        )
        if is_compatible:
            return current
        current = get_node_parent(store, current)
    return None
```

#### New `get_sg_root`

*Note*: The anchor of every walk: the active prefix of the saved grade-1 node,
and the FG root when there is no grade-1 node or the root has passed it. A fresh
SG root in use at an honest validator holds grade 0 in every honest store that
admits its supporting votes, so the grade-0 veto protects it everywhere.

```python
def get_sg_root(store: Store) -> ForkChoiceNode:
    prefix = get_active_prefix(store, store.grade_1)
    if prefix is not None:
        return prefix
    return ForkChoiceNode(root=get_fg_root(store), payload_status=PAYLOAD_STATUS_PENDING)
```

#### New `is_grade_0_compatible`

```python
def is_grade_0_compatible(store: Store, node: ForkChoiceNode) -> bool:
    veto = store.grade_0
    if veto is None or veto.root not in store.blocks or node.root not in store.blocks:
        return True
    return is_ancestor(store, node, veto) or is_ancestor(store, veto, node)
```

#### New `get_stable_root`

```python
def get_stable_root(store: Store) -> ForkChoiceNode:
    prefix = get_active_prefix(store, store.grade_2)
    if prefix is not None:
        return prefix
    return ForkChoiceNode(root=get_fg_root(store), payload_status=PAYLOAD_STATUS_PENDING)
```

#### New `get_safe_vote_node`

*Note*: The node an honest validator names in its safe vote: the deepest
grade-0-compatible node between the anchor and the confirmed node; the grade-2
active prefix when there is none; the FG root when grade 2 exists but the root
has passed it; and the anchor as the final fallback, which keeps voting total.

```python
def get_safe_vote_node(store: Store) -> ForkChoiceNode:
    anchor = get_sg_root(store)
    confirmed = store.confirmed
    if is_ancestor(store, confirmed, anchor):
        current: ForkChoiceNode | None = confirmed
        while current is not None:
            if is_grade_0_compatible(store, current):
                return current
            if current == anchor:
                break
            current = get_node_parent(store, current)
    grade_2_prefix = get_active_prefix(store, store.grade_2)
    if grade_2_prefix is not None:
        return grade_2_prefix
    if store.grade_2 is not None:
        return ForkChoiceNode(root=get_fg_root(store), payload_status=PAYLOAD_STATUS_PENDING)
    return anchor
```

### Head selection

#### Modified `get_head`

*Note*: `get_head` is rewritten entirely. It takes the slot whose votes weigh
the walk: the proposer of slot `s` uses the votes of slot `s - 1`, and the FG
attestation source uses the votes of the current slot. Called without a vote
slot, it uses the latest complete generation, the previous slot's votes. The
support set is the resolved subset of the pool. Duties that must not be
influenced by late arrivals use `get_voter_head` instead.

```python
def get_head(store: Store, vote_slot: Slot | None = None) -> ForkChoiceNode:
    if vote_slot is None:
        current_slot = get_current_slot(store)
        vote_slot = Slot(current_slot - 1) if current_slot > GENESIS_SLOT else GENESIS_SLOT
    committee = get_head_vote_committee_at_slot(store, vote_slot)
    votes = get_slot_head_votes(store, vote_slot)
    support_votes = [vote for vote in votes if get_resolution_time_ms(store, vote) is not None]
    anchor = get_sg_root(store)
    view = get_filtered_roots(store)
    return compute_goldfish_head(
        store, anchor, view, committee, votes, support_votes, majority_only=False
    )
```

#### New `get_voter_head`

This is the AC voting procedure of the
[validator guide](./validator.md#head-vote-data): view merge, then the
restricted walk. It is the paper's `goldfish_vote` view construction together
with `voter_filtered_block_tree`.

The voter at slot `s` forms two vote sets. The set `votes` holds each slot
`s - 1` vote that the store received before the view freeze of slot `s - 1`,
together with every slot `s - 1` vote included in a slot-`s` proposal. The
subset `support_votes` holds the local votes resolved before the freeze,
together with each proposal-carried vote whose support bit is set and whose head
is held by voting time and is a block of slot at most `s - 1`. The proposer's
support bits are taken as published: a carried vote with a cleared bit stays
outside `support_votes` even if it resolves locally, and the carried support
does not require a local receipt. Participation and equivocation are determined
by `votes`, regardless of resolution, while `support_votes` determines subtree
support.

The walk runs inside a block view formed the same way: blocks received before
the freeze, together with every ancestor of a slot-`s` proposal. A late witness
cannot make an old pre-freeze child enter this vote's walk.

```python
def get_voter_head(store: Store, slot: Slot) -> ForkChoiceNode:
    vote_slot = Slot(slot - 1)
    freeze_ms = compute_time_at_slot_ms(store.genesis_time_ms, vote_slot) + get_view_freeze_due_ms()
    committee = get_head_vote_committee_at_slot(store, vote_slot)

    votes = [vote for vote in get_slot_head_votes(store, vote_slot) if vote.arrival_ms < freeze_ms]
    support_votes = []
    for vote in votes:
        resolution_ms = get_resolution_time_ms(store, vote)
        if resolution_ms is not None and resolution_ms < freeze_ms:
            support_votes.append(vote)

    # Merge the views published by the current slot's proposals
    proposals = [root for root in store.blocks if store.blocks[root].slot == slot]
    for proposal_root in proposals:
        body = store.blocks[proposal_root].body
        for vote_index in range(len(body.head_votes)):
            aggregate = body.head_votes[vote_index]
            if aggregate.data.slot != vote_slot:
                continue
            support_bits = body.head_vote_support[vote_index]
            for position, validator_index in enumerate(aggregate.voter_indices):
                carried = StoreHeadVote(
                    validator_index=validator_index,
                    data=aggregate.data,
                    arrival_ms=freeze_ms,
                )
                if not has_head_vote(votes, carried):
                    votes.append(carried)
                is_resolvable = (
                    aggregate.data.beacon_block_root in store.blocks
                    and store.blocks[aggregate.data.beacon_block_root].slot <= vote_slot
                )
                if support_bits[position] and is_resolvable:
                    if not has_head_vote(support_votes, carried):
                        support_votes.append(carried)

    # The vote-domain merge has a block-domain analogue
    blocks_view: set[Root] = set()
    for root in store.blocks:
        if store.block_arrivals_ms[root] < freeze_ms:
            blocks_view.add(root)
        else:
            for proposal_root in proposals:
                if is_ancestor_root(store, root, proposal_root):
                    blocks_view.add(root)
                    break

    anchor = get_sg_root(store)
    view = get_filtered_roots_from(store, blocks_view)
    return compute_goldfish_head(
        store, anchor, view, committee, votes, support_votes, majority_only=False
    )
```

#### New `has_head_vote`

```python
def has_head_vote(votes: Sequence[StoreHeadVote], vote: StoreHeadVote) -> bool:
    return any(
        existing.validator_index == vote.validator_index and existing.data == vote.data
        for existing in votes
    )
```

### Confirmation

#### New `update_confirmation`

*Note*: This is the paper's `update_confirmation`, evaluated for slot `slot` at
the support cutoff of the following slot. Support counts only the votes resolved
before the slot's own support cutoff and not contradicted by a second distinct
vote of the same validator received before evaluation time; participation counts
every vote received before evaluation time. The protocol-facing `confirmed`
takes the walk's result when the result itself holds a strict majority, and
falls back to the FG root otherwise, with the saved grade-2 node standing in for
the walk in the user-facing record. The FG root sits below every voting floor,
so an unconfirmed slot restricts nothing further.

```python
def update_confirmation(store: Store, slot: Slot) -> None:
    early_cutoff_ms = (
        compute_time_at_slot_ms(store.genesis_time_ms, slot) + get_head_vote_support_due_ms()
    )
    late_cutoff_ms = (
        compute_time_at_slot_ms(store.genesis_time_ms, Slot(slot + 1))
        + get_head_vote_support_due_ms()
    )
    committee = get_head_vote_committee_at_slot(store, slot)

    late_votes = [
        vote for vote in get_slot_head_votes(store, slot) if vote.arrival_ms < late_cutoff_ms
    ]
    equivocating = get_equivocating_voters(late_votes)
    support_votes = []
    for vote in late_votes:
        resolution_ms = get_resolution_time_ms(store, vote)
        if resolution_ms is None or resolution_ms >= early_cutoff_ms:
            continue
        if vote.validator_index in equivocating:
            continue
        support_votes.append(vote)

    anchor = get_sg_root(store)
    view = get_filtered_roots(store)
    head = compute_goldfish_head(
        store, anchor, view, committee, late_votes, support_votes, majority_only=True
    )
    head_weight = get_goldfish_weight(store, committee, late_votes, support_votes, head)
    if 2 * head_weight > get_participating_seats(committee, late_votes):
        store.confirmed = head
        candidate: ForkChoiceNode | None = head
    else:
        store.confirmed = ForkChoiceNode(
            root=get_fg_root(store), payload_status=PAYLOAD_STATUS_PENDING
        )
        # The saved grade-2 node stands in for the walk
        candidate = get_active_prefix(store, store.grade_2)
    update_confirmation_records(store, candidate)
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

#### New `update_confirmation_records`

*Note*: The confirmation record's write is floored on the stable record, in the
same duty and after it: the candidate is recorded when it extends the new stable
record; the old record is kept while it still does; and only when the stable
record has left the old record's chain does the confirmation record move to the
stable record itself. By these three cases alone, with no fault bound,
`latest_stable ⪯ latest_confirmed` at every node and every time, and the floor
never undoes the record's own progress.

```python
def update_confirmation_records(store: Store, candidate: ForkChoiceNode | None) -> None:
    new_confirmed = advance_record(store, store.latest_confirmed, candidate)
    store.latest_stable = advance_record(store, store.latest_stable, get_stable_root(store))
    stable = store.latest_stable
    if new_confirmed == stable or is_ancestor(store, new_confirmed, stable):
        store.latest_confirmed = new_confirmed
    elif not (
        store.latest_confirmed == stable or is_ancestor(store, store.latest_confirmed, stable)
    ):
        store.latest_confirmed = stable
```

#### New `get_stable`

*Note*: User-facing; no voting rule reads it. It backs the stable chain, one
layer above finality and one below the available chain.

```python
def get_stable(store: Store) -> ForkChoiceNode:
    finalized_root = store.finalized_checkpoint.root
    if is_ancestor_root(store, finalized_root, store.latest_stable.root):
        return store.latest_stable
    return ForkChoiceNode(root=finalized_root, payload_status=PAYLOAD_STATUS_PENDING)
```

#### New `get_confirmed`

*Note*: User-facing; no voting rule reads it. The confirmed tip floors on the
stable tip rather than directly on finality, so the four tips nest at every node
and every time: `finalized ⪯ get_stable ⪯ get_confirmed ⪯ head` under the
protocol's assumptions.

```python
def get_confirmed(store: Store) -> ForkChoiceNode:
    stable = get_stable(store)
    confirmed = store.latest_confirmed
    if confirmed == stable or is_ancestor(store, confirmed, stable):
        return confirmed
    return stable
```

### FG summary

#### New `update_finality`

*Note*: This is the paper's `update_finality`. The justified checkpoint tracks
the lex-greatest justification compatible with the finalized block. The
finalized checkpoint advances only to a viable proper descendant of itself below
the justified checkpoint, so `F ⪯ J` always holds and finalization never
reverts. Checkpoint roots are entry blocks of the chain that produced the state,
so a summary whose root is not yet held is folded when a later block of that
chain arrives.

```python
def update_finality(store: Store, state: BeaconState) -> None:
    store.max_height = max(store.max_height, state.target_checkpoint.height)

    justified = state.justified_checkpoint
    if justified.root in store.blocks:
        if is_ancestor_root(store, store.finalized_checkpoint.root, justified.root):
            store_justified = store.justified_checkpoint
            if (justified.height, justified.root) > (store_justified.height, store_justified.root):
                store.justified_checkpoint = justified

    finalized = state.finalized_checkpoint
    if finalized.root in store.blocks:
        is_advance = (
            finalized.height > store.finalized_checkpoint.height
            and is_ancestor_root(store, store.finalized_checkpoint.root, finalized.root)
            and is_ancestor_root(store, finalized.root, store.justified_checkpoint.root)
            and is_viable_root(store, finalized.root)
        )
        if is_advance:
            store.finalized_checkpoint = finalized
            store.finalized_slot = state.finalized_slot
            # A finality advance cuts every saved grade back to its deepest
            # ancestor compatible with the new finalized block
            store.grade_2 = clip_node_to_finalized(store, store.grade_2)
            store.grade_1 = clip_node_to_finalized(store, store.grade_1)
            store.grade_0 = clip_node_to_finalized(store, store.grade_0)
```

### FG attestation sources

The FG reads two things back from the available chain. The *target source* is
the confirmed block: a target vote can create a justification, and only
confirmed blocks may be justified. The *finality source* is the head: its
subject is already justified, so it may read an unconfirmed chain, and the head
chain state holds the freshest justification. The
[validator guide](./validator.md#attesting) builds `AttestationData` from these
two states together with the validator's signing record; the record itself
belongs to the validator client and is out of scope here.

#### New `get_fg_target_source`

```python
def get_fg_target_source(store: Store) -> BeaconState:
    return store.block_states[store.confirmed.root]
```

#### New `get_fg_finality_source`

```python
def get_fg_finality_source(store: Store) -> BeaconState:
    head = get_head(store, get_current_slot(store))
    return store.block_states[head.root]
```

#### New `has_fresh_safe_quorum`

*Note*: A validator emits a height pair only in rounds with an active grade-2
node — fresh quorum evidence from the stabilization layer. Without it, the
attestation carries its finality pair alone.

```python
def has_fresh_safe_quorum(store: Store) -> bool:
    return get_active_prefix(store, store.grade_2) is not None
```

## Handlers

### Modified `on_tick`

*Note*: Besides advancing the clock, the tick evaluates the confirmation of slot
`s - 1` once the support cutoff of slot `s` has passed, each slot evaluated at
most once. A node that ticks sparsely evaluates only the most recent due slot;
the cutoffs are receipt-time comparisons, so a late evaluation reads the same
sets a timely one would have.

```python
def on_tick(store: Store, time_ms: Uint64) -> None:
    store.time_ms = time_ms
    update_grades(store)
    current_slot = get_current_slot(store)
    if current_slot <= GENESIS_SLOT + 1:
        return
    confirmation_due_ms = (
        compute_time_at_slot_ms(store.genesis_time_ms, current_slot)
        + get_head_vote_support_due_ms()
    )
    if time_ms >= confirmation_due_ms:
        evaluation_slot = Slot(current_slot - 1)
    else:
        evaluation_slot = Slot(current_slot - 2)
    if evaluation_slot > store.confirmation_slot:
        update_confirmation(store, evaluation_slot)
        store.confirmation_slot = evaluation_slot
```

### Modified `on_block`

*Note*: The checkpoint logic of prior forks is replaced: the descendant check
runs against the finalized height checkpoint, the post-state's FG summary is
folded by `update_finality`, and the block's carried head votes pass through
`record_head_vote` under the same admission rule as a wire receipt. The state
transition has already verified each carried vote's committee, signature and
support-bit slot rule. There is no proposer boost.

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

    # Blocks cannot be in the future. If they are, their consideration must be
    # delayed until they are in the past.
    assert get_current_slot(store) >= block.slot

    # [Modified in EIP8453]
    # Check the block is a descendant of the finalized block
    assert block.slot > store.finalized_slot
    parent_node = ForkChoiceNode(root=block.parent_root, payload_status=PAYLOAD_STATUS_PENDING)
    finalized_ancestor = get_ancestor(store, parent_node, store.finalized_slot)
    assert finalized_ancestor.root == store.finalized_checkpoint.root

    # Make a copy of the state to avoid mutability issues
    state = store.block_states[block.parent_root].copy()

    # Check the block is valid and compute the post-state
    state_transition(state, signed_block, validate_result=True)

    # Add new block and state to the store
    store.blocks[block_root] = block
    store.block_states[block_root] = state
    # [New in EIP8453]
    store.block_arrivals_ms[block_root] = store.time_ms
    store.payload_timeliness_vote[block_root] = [None] * PTC_SIZE
    store.payload_data_availability_vote[block_root] = [None] * PTC_SIZE

    # Notify the store about the payload_attestations in the block
    notify_ptc_messages(store, state, block.body.payload_attestations)

    record_block_timeliness(store, block_root)

    # [New in EIP8453]
    # Carried head votes enter the pool under the wire admission rule
    for head_vote in block.body.head_votes:
        for validator_index in head_vote.voter_indices:
            record_head_vote(store, validator_index, head_vote.data)

    # [New in EIP8453]
    # Fold the post-state's FG summary into the store
    update_finality(store, state)

    # [New in EIP8453]
    # Carried safe votes enter the pool after the finality update,
    # under the same admission rule as a wire receipt
    for safe_vote in block.body.safe_votes:
        for validator_index in safe_vote.voter_indices:
            record_safe_vote(store, validator_index, safe_vote.data)
```

### New `record_head_vote`

*Note*: This is the paper's `on_goldfish_vote`. The pool ignores votes older
than the previous slot or from a future slot, accepts each vote at most once,
and keeps at most two distinct votes per validator per slot — all any rule
reads. Blocks may carry votes of earlier slots for builder payment accounting;
those are the state transition's business and do not enter the pool. A refused
vote is not consumed: a later delivery may be admitted after the guard changes.

```python
def record_head_vote(store: Store, validator_index: ValidatorIndex, data: HeadVoteData) -> None:
    current_slot = get_current_slot(store)
    if data.slot + 1 < current_slot or data.slot > current_slot:
        return
    committee = get_head_vote_committee_at_slot(store, data.slot)
    if validator_index not in committee:
        return
    if data.slot not in store.head_votes:
        store.head_votes[data.slot] = []
    votes = store.head_votes[data.slot]
    distinct: list[HeadVoteData] = []
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
        StoreHeadVote(validator_index=validator_index, data=data, arrival_ms=store.time_ms)
    )
```

### New `on_head_vote`

*Note*: Run upon receiving a `HeadVoteMessage` on the wire, or upon decomposing
a `HeadVote` aggregate into its voters. Signature verification is a gossip
concern, specified in the [networking guide](./p2p-interface.md); the state
transition re-verifies the votes a block carries.

```python
def on_head_vote(store: Store, message: HeadVoteMessage) -> None:
    data = message.data
    assert data.payload_status in (
        PAYLOAD_STATUS_EMPTY,
        PAYLOAD_STATUS_FULL,
        PAYLOAD_STATUS_PENDING,
    )
    record_head_vote(store, message.validator_index, data)
```

### New `record_safe_vote`

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

### New `on_safe_vote`

*Note*: Run upon receiving a `SafeVoteMessage` on the wire, or upon decomposing
a `SafeVote` aggregate into its voters. Signature and membership verification
are gossip concerns, specified in the [networking guide](./p2p-interface.md);
the state transition re-verifies the votes a block carries.

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

## Divergences from the paper

This draft follows §7 of the paper (`verified-consensus/docs/PROTOCOL.md`) with
these deliberate departures, each tracking a decision already made elsewhere in
this upgrade:

1. **Seats, not validators.** The paper fixes a committee `𝒦_s` with an honest
   majority of members; this upgrade samples `HEAD_VOTE_COMMITTEE_SIZE` seats by
   effective balance, with duplicates. Every score and majority here counts
   seats, matching the state transition's builder payment accounting.
2. **Payload-status nodes.** The paper's fork choice walks blocks; this upgrade
   walks `(root, payload_status)` nodes as in Gloas, and `HeadVoteData` names a
   payload status. Votes for different payload statuses with the same root are
   distinct votes by the equivocation rule.
3. **A separate safe-vote message.** The paper's SG votes ride the combined
   attestation's `safe` field; this upgrade carries them as their own wire
   object, the [safe vote](./beacon-chain.md#new-safevotedata), signed
   separately so FG attestation aggregation is untouched and safe votes
   aggregate by value across the whole set. The grades read only the safe votes,
   so the split changes nothing they consume. Unlike the paper's single
   per-round action instant, safe votes are cast across the first
   `SLOTS_PER_ROUND - 2` sub-rounds of the round — after the round's grades
   complete and early enough to arrive before the next round's earliest cutoff.
   The paper's theorems are being re-established for this *vote window* schedule
   in the Lean development; the single instant is the zero-width instance.
4. **Committee dependence.** The paper's committees are an oracle; here
   committees and stabilization weights are computed from the latest finalized
   block's post-state, which is stable across branches. During prolonged
   non-finality this state ages; advancing it is a hardening question for the
   normative specification.
5. **Timeout delay.** The beacon chain sets `TIMEOUT_DELAY_SLOTS` to two rounds,
   matching the paper's `δ_t = 2R`; its liveness results are proved for
   `δ_t = (2 + e)R`, `e ≥ 0`.
6. **Sparse ticks.** The paper runs every public time's tick exactly once; this
   document evaluates only the most recent due confirmation when ticks are
   sparse.

The proposer-side duties — building `head_votes` and `head_vote_support` from
the proposal view, and choosing the parent with `get_head` over the previous
slot's votes — are specified in the [validator guide](./validator.md). The
anti-slashing record and the attestation construction rules it feeds are also
validator-side, reading `get_fg_target_source` and `get_fg_finality_source`.
