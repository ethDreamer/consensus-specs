# Trident -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Time parameters](#time-parameters)
- [Constants](#constants)
- [Helpers](#helpers)
  - [Time](#time)
    - [New `get_delta_ms`](#new-get_delta_ms)
    - [New `compute_slot_start_ms`](#new-compute_slot_start_ms)
    - [New `compute_round_start_ms`](#new-compute_round_start_ms)
    - [New `compute_attestation_time_ms`](#new-compute_attestation_time_ms)
    - [New `get_current_slot`](#new-get_current_slot)
    - [New `get_current_round`](#new-get_current_round)
  - [Vote records](#vote-records)
  - [New `Store`](#new-store)
  - [New `get_forkchoice_store`](#new-get_forkchoice_store)
  - [Chain predicates](#chain-predicates)
    - [New `is_ancestor`](#new-is_ancestor)
    - [New `is_compatible`](#new-is_compatible)
    - [New `get_deepest`](#new-get_deepest)
  - [Resolution](#resolution)
    - [New `get_goldfish_resolution_time_ms`](#new-get_goldfish_resolution_time_ms)
    - [New `get_attestation_resolution_time_ms`](#new-get_attestation_resolution_time_ms)
  - [Viability and derived trees](#viability-and-derived-trees)
    - [New `get_viable_blocks_from`](#new-get_viable_blocks_from)
    - [New `get_viable_blocks`](#new-get_viable_blocks)
    - [New `get_fg_root`](#new-get_fg_root)
    - [New `get_filtered_block_tree_from`](#new-get_filtered_block_tree_from)
    - [New `get_filtered_block_tree`](#new-get_filtered_block_tree)
  - [Goldfish score and walk](#goldfish-score-and-walk)
    - [New `get_goldfish_committee_for`](#new-get_goldfish_committee_for)
    - [New `get_goldfish_score`](#new-get_goldfish_score)
    - [New `count_goldfish_voters`](#new-count_goldfish_voters)
    - [New `get_children`](#new-get_children)
    - [New `goldfish_fork_choice`](#new-goldfish_fork_choice)
  - [Grades](#grades)
    - [New `get_attestation_weight`](#new-get_attestation_weight)
    - [New `get_window_rounds`](#new-get_window_rounds)
    - [New `get_resolved_votes`](#new-get_resolved_votes)
    - [New `covers`](#new-covers)
    - [New `equivocates_since`](#new-equivocates_since)
    - [New `supports`](#new-supports)
    - [New `opposes`](#new-opposes)
    - [New `get_window_validators`](#new-get_window_validators)
    - [New `holds_relative_majority`](#new-holds_relative_majority)
    - [New `get_graded_block`](#new-get_graded_block)
    - [New `update_grades`](#new-update_grades)
    - [New `get_active_prefix`](#new-get_active_prefix)
    - [New `is_grade_0_compatible`](#new-is_grade_0_compatible)
    - [New `get_sg_root`](#new-get_sg_root)
  - [Head](#head)
    - [New `get_head_in_tree`](#new-get_head_in_tree)
    - [New `get_head_with_votes`](#new-get_head_with_votes)
    - [New `get_head`](#new-get_head)
  - [Confirmation](#confirmation)
    - [New `advance_record`](#new-advance_record)
    - [New `get_stable_root_candidate`](#new-get_stable_root_candidate)
    - [New `update_user_confirmation_records`](#new-update_user_confirmation_records)
    - [New `update_confirmation`](#new-update_confirmation)
    - [New `get_stable`](#new-get_stable)
    - [New `get_confirmed`](#new-get_confirmed)
  - [Payload status](#payload-status)
    - [New `get_payload_status_in_chain`](#new-get_payload_status_in_chain)
    - [Modified `should_build_on_full`](#modified-should_build_on_full)
- [Handlers](#handlers)
  - [New `update_finality`](#new-update_finality)
  - [New `cut_to_compatible`](#new-cut_to_compatible)
  - [New `on_goldfish_vote`](#new-on_goldfish_vote)
  - [New `on_trident_attestation`](#new-on_trident_attestation)
  - [New `on_block`](#new-on_block)
  - [New `on_tick`](#new-on_tick)

<!-- mdformat-toc end -->

## Introduction

This document specifies the Trident fork choice: the cumulative node store, its
handlers, the Goldfish fork choice composed with the finality-gadget filter, the
three stabilization grades, and the confirmation rule. It supersedes the
inherited fork choice wholesale; the inherited `on_attestation` and
`on_attester_slashing` handlers are unused. It transcribes the complete protocol
(Section 7) of the `verified-consensus` formalization.

The store exposes three nested tips: the finalized chain with tip
`store.finalized_root`, the stable chain with tip `get_stable(store)`, and the
available chain with tip `get_confirmed(store)`. The nesting
`finalized <= stable <= confirmed` holds by construction of the two accessors
alone, with no fault bound or synchrony hypothesis.

*Note*: Under ePBS, a block's payload status (*full* or *empty*) is committed by
the next beacon block on each branch: the child's bid names the parent payload
it builds on (`get_parent_payload_status`, unchanged from Gloas). A
full-versus-empty disagreement about a block therefore materializes as two
conflicting children, which is an ordinary fork of the block tree, so the walk,
the grades, and the tips below operate on plain blocks, exactly the abstraction
of the verified model. Payload status is a frontier phenomenon only: it is
undecided precisely at a chain's tip, where the PTC view informs the next
proposer's commitment (`should_build_on_full`). Goldfish votes carry no payload
bit, since they expire after one slot and are never reinterpreted as support for
an old payload decision. The payload envelope and PTC handlers
(`on_execution_payload_envelope`, `on_payload_attestation_message`) are
unchanged from Gloas. The node-weighted payload fork choice of Gloas
(`ForkChoiceNode`, the payload-status tiebreaker, proposer boost) is superseded:
a bid committing to an unavailable payload produces a child that fails the
Goldfish majority eligibility and is orphaned by the standard mechanism.

## Time parameters

The slot is divided into four intervals of `DELTA_MS` each. `DELTA_MS` is the
network delay bound of the protocol's schedule: proposal at the slot start,
Goldfish vote one interval in, support cutoff at two, view freeze at three. The
slot-`s` confirmation evaluation runs at six intervals, which is two intervals
into slot `s + 1`. A round opens at the proposal time of its opening slot,
written `T_r`; the round's attestation time is `a_r = T_r + 6 * DELTA_MS`.

| Name                         | Value       |
| ---------------------------- | ----------- |
| `INTERVALS_PER_SLOT_TRIDENT` | `Uint64(4)` |

## Constants

| Name               | Value               |
| ------------------ | ------------------- |
| `TIME_MS_INFINITY` | `Uint64(2**64 - 1)` |

## Helpers

### Time

#### New `get_delta_ms`

```python
def get_delta_ms() -> Uint64:
    return Uint64(SLOT_DURATION_MS // INTERVALS_PER_SLOT_TRIDENT)
```

#### New `compute_slot_start_ms`

```python
def compute_slot_start_ms(store: Store, slot: Slot) -> Uint64:
    return compute_time_at_slot_ms(store.genesis_time_ms, slot)
```

#### New `compute_round_start_ms`

```python
def compute_round_start_ms(store: Store, round: Round) -> Uint64:
    return compute_slot_start_ms(store, compute_round_opening_slot(round))
```

#### New `compute_attestation_time_ms`

```python
def compute_attestation_time_ms(store: Store, round: Round) -> Uint64:
    return Uint64(compute_round_start_ms(store, round) + 6 * get_delta_ms())
```

#### New `get_current_slot`

```python
def get_current_slot(store: Store) -> Slot:
    return compute_slot_at_time_ms(store.genesis_time_ms, store.time_ms)
```

#### New `get_current_round`

```python
def get_current_round(store: Store) -> Round:
    return compute_round_at_slot(get_current_slot(store))
```

### Vote records

The pool keeps processed objects with their processing timestamps, and nothing
else: every rule below is a timestamp comparison on this one pool. An
attestation record keeps the combined attestation in full where it is known, but
every stabilization rule and grade reads only the stabilization projection
`(validator_index, round, safe_root)`.

```python
@dataclass
class GoldfishVoteRecord:
    validator_index: ValidatorIndex
    slot: Slot
    head_root: Root
    time_ms: Uint64
```

```python
@dataclass
class AttestationRecord:
    validator_index: ValidatorIndex
    stabilization: StabilizationData
    finality: FinalityData | None
    time_ms: Uint64
```

### New `Store`

```python
@dataclass
class Store:
    time_ms: Uint64
    genesis_time_ms: Uint64
    blocks: dict[Root, BeaconBlock]
    block_states: dict[Root, BeaconState]
    block_times_ms: dict[Root, Uint64]
    goldfish_votes: dict[Slot, list[GoldfishVoteRecord]]
    attestation_pool: dict[Round, list[AttestationRecord]]
    payloads: dict[Root, ExecutionPayloadEnvelope]
    payload_timeliness_vote: dict[Root, list[Boolean | None]]
    payload_data_availability_vote: dict[Root, list[Boolean | None]]
    payload_inclusion_list_satisfaction: dict[Root, bool]
    grade_2_root: Root | None
    grade_1_root: Root | None
    grade_0_root: Root | None
    finalized_root: Root
    justified_root: Root
    justified_height: Height
    max_height: Height
    live_confirmed_root: Root
    latest_confirmed_root: Root
    latest_stable_root: Root
```

### New `get_forkchoice_store`

The anchor plays the role of the genesis block: it is the initial finalized,
justified, confirmed and stable tip. A node that joins starts with empty grade
fields and does not reconstruct a missed grade; its first complete set of grades
is the next round's.

```python
def get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock) -> Store:
    assert anchor_block.state_root == hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block)
    genesis_time_ms = seconds_to_milliseconds(anchor_state.genesis_time)
    return Store(
        time_ms=compute_time_at_slot_ms(genesis_time_ms, anchor_state.slot),
        genesis_time_ms=genesis_time_ms,
        blocks={anchor_root: anchor_block.copy()},
        block_states={anchor_root: anchor_state.copy()},
        block_times_ms={anchor_root: Uint64(0)},
        goldfish_votes={},
        attestation_pool={},
        payloads={},
        payload_timeliness_vote={anchor_root: [None] * PTC_SIZE},
        payload_data_availability_vote={anchor_root: [None] * PTC_SIZE},
        payload_inclusion_list_satisfaction={},
        grade_2_root=None,
        grade_1_root=None,
        grade_0_root=None,
        finalized_root=anchor_root,
        justified_root=anchor_root,
        justified_height=anchor_state.latest_justified.height,
        max_height=anchor_state.height,
        live_confirmed_root=anchor_root,
        latest_confirmed_root=anchor_root,
        latest_stable_root=anchor_root,
    )
```

### Chain predicates

#### New `is_ancestor`

`is_ancestor(store, a, b)` is the ancestry relation `a <= b` on processed
blocks: `a` equals `b` or `a` is an ancestor of `b`.

```python
def is_ancestor(store: Store, ancestor_root: Root, descendant_root: Root) -> bool:
    if ancestor_root not in store.blocks or descendant_root not in store.blocks:
        return False
    ancestor_slot = store.blocks[ancestor_root].slot
    root = descendant_root
    while root in store.blocks and store.blocks[root].slot > ancestor_slot:
        root = store.blocks[root].parent_root
    return root == ancestor_root
```

#### New `is_compatible`

Two blocks are compatible when one is an ancestor of the other; they conflict
otherwise.

```python
def is_compatible(store: Store, root_1: Root, root_2: Root) -> bool:
    return is_ancestor(store, root_1, root_2) or is_ancestor(store, root_2, root_1)
```

#### New `get_deepest`

"Deepest" means maximum depth from genesis; ties use the root order. Within one
chain the slot orders blocks by depth, and the callers below compare blocks that
provably lie on one chain, so `(slot, root)` is a sound total order.

```python
def get_deepest(store: Store, roots: list[Root]) -> Root | None:
    if len(roots) == 0:
        return None
    best = roots[0]
    for root in roots[1:]:
        if (store.blocks[root].slot, root) > (store.blocks[best].slot, best):
            best = root
    return best
```

### Resolution

A Goldfish vote is resolved when the store holds its head and the head is a
block of the vote's slot or earlier; a vote whose head is a later-slot block
stays in the pool as a cast vote but never resolves. An attestation resolves at
the later of its own and its safe block's timestamps; an empty safe block
resolves at receipt.

#### New `get_goldfish_resolution_time_ms`

```python
def get_goldfish_resolution_time_ms(store: Store, record: GoldfishVoteRecord) -> Uint64:
    if record.head_root not in store.blocks:
        return TIME_MS_INFINITY
    if store.blocks[record.head_root].slot > record.slot:
        return TIME_MS_INFINITY
    return max(record.time_ms, store.block_times_ms[record.head_root])
```

#### New `get_attestation_resolution_time_ms`

```python
def get_attestation_resolution_time_ms(store: Store, record: AttestationRecord) -> Uint64:
    safe_root = record.stabilization.safe_root
    if safe_root == Root():
        return record.time_ms
    if safe_root not in store.blocks:
        return TIME_MS_INFINITY
    return max(record.time_ms, store.block_times_ms[safe_root])
```

### Viability and derived trees

#### New `get_viable_blocks_from`

A descendant of the finalized block is viable when one of its descendants has
state height at most one below the current maximum.

```python
def get_viable_blocks_from(store: Store, block_roots: list[Root]) -> list[Root]:
    viable = []
    for root in block_roots:
        if not is_ancestor(store, store.finalized_root, root):
            continue
        for other in block_roots:
            if (
                is_ancestor(store, root, other)
                and store.block_states[other].height + 1 >= store.max_height
            ):
                viable.append(root)
                break
    return viable
```

#### New `get_viable_blocks`

```python
def get_viable_blocks(store: Store) -> list[Root]:
    return get_viable_blocks_from(store, list(store.blocks.keys()))
```

#### New `get_fg_root`

```python
def get_fg_root(store: Store) -> Root:
    if store.max_height == store.justified_height + 1:
        return store.justified_root
    return store.finalized_root
```

#### New `get_filtered_block_tree_from`

```python
def get_filtered_block_tree_from(store: Store, block_roots: list[Root]) -> list[Root]:
    root = get_fg_root(store)
    return [
        block_root
        for block_root in get_viable_blocks_from(store, block_roots)
        if is_ancestor(store, root, block_root)
    ]
```

#### New `get_filtered_block_tree`

```python
def get_filtered_block_tree(store: Store) -> list[Root]:
    return get_filtered_block_tree_from(store, list(store.blocks.keys()))
```

### Goldfish score and walk

#### New `get_goldfish_committee_for`

The committee of a vote slot, read from the fork-choice store. The FG-root state
is advanced to the slot's epoch when it lags (the advance crosses the epoch
transition, which writes the snapshot that `get_goldfish_committee_at` reads); a
state already past the slot's epoch serves the snapshot directly. All scoring,
decoding, and duty consumers in this document and the validator document read
committees through this one accessor, so every honest node with the same FG root
decodes the same committee.

```python
def get_goldfish_committee_for(store: Store, slot: Slot) -> list[ValidatorIndex]:
    state = store.block_states[get_fg_root(store)]
    target_epoch = compute_epoch_at_slot(slot)
    if get_current_epoch(state) < target_epoch:
        state = state.copy()
        process_slots(state, compute_start_slot_at_epoch(target_epoch))
    return get_goldfish_committee_at(state, slot)
```

#### New `get_goldfish_score`

Scores count committee *seats*. A validator's support, participation, and
equivocation are per-validator facts that apply to every seat it occupies, so a
validator occupying several seats contributes its full multiplicity, independent
of which bits an aggregator happened to set. Equivocators count for every block
and stay among the participants: discovering an equivocation cannot make a
majority-eligible block ineligible, though it can make another block newly
eligible. A non-equivocating validator's seats count once, in one subtree. The
score counts seats, not stake.

```python
def get_goldfish_score(
    store: Store,
    committee: list[ValidatorIndex],
    votes: list[GoldfishVoteRecord],
    support_votes: list[GoldfishVoteRecord],
    block_root: Root,
) -> Uint64:
    equivocators = set()
    voters = set()
    for record in votes:
        if record.validator_index in voters:
            distinct = [
                other
                for other in votes
                if other.validator_index == record.validator_index
                and other.head_root != record.head_root
            ]
            if len(distinct) > 0:
                equivocators.add(record.validator_index)
        voters.add(record.validator_index)
    supporters = set()
    for record in support_votes:
        if record.validator_index in equivocators:
            continue
        if is_ancestor(store, block_root, record.head_root):
            supporters.add(record.validator_index)
    seats = 0
    for index in committee:
        if index in equivocators or index in supporters:
            seats += 1
    return Uint64(seats)
```

#### New `count_goldfish_voters`

```python
def count_goldfish_voters(
    committee: list[ValidatorIndex], votes: list[GoldfishVoteRecord]
) -> Uint64:
    voters = {record.validator_index for record in votes}
    seats = 0
    for index in committee:
        if index in voters:
            seats += 1
    return Uint64(seats)
```

#### New `get_children`

```python
def get_children(store: Store, tree_roots: list[Root], block_root: Root) -> list[Root]:
    return [root for root in tree_roots if store.blocks[root].parent_root == block_root]
```

#### New `goldfish_fork_choice`

The GHOST walk descends from the anchor through eligible children, taking the
highest score at each step, ties by root order, and stops where no child is
eligible. A child is eligible when its parent's state height is below the height
band, when it holds a strict majority of the voters, or when it is a
current-slot proposal, which cannot yet have votes.

```python
def goldfish_fork_choice(
    store: Store,
    anchor_root: Root,
    tree_roots: list[Root],
    committee: list[ValidatorIndex],
    votes: list[GoldfishVoteRecord],
    support_votes: list[GoldfishVoteRecord],
) -> Root:
    voters_count = count_goldfish_voters(committee, votes)
    current_slot = get_current_slot(store)
    head = anchor_root
    while True:
        eligible_children = []
        for child in get_children(store, tree_roots, head):
            parent_state = store.block_states[store.blocks[child].parent_root]
            score = get_goldfish_score(store, committee, votes, support_votes, child)
            if (
                parent_state.height + 1 < store.max_height
                or 2 * score > voters_count
                or store.blocks[child].slot == current_slot
            ):
                eligible_children.append(child)
        if len(eligible_children) == 0:
            return head
        best = eligible_children[0]
        best_score = get_goldfish_score(store, committee, votes, support_votes, best)
        for child in eligible_children[1:]:
            score = get_goldfish_score(store, committee, votes, support_votes, child)
            if (score, child) > (best_score, best):
                best = child
                best_score = score
        head = best
```

### Grades

#### New `get_attestation_weight`

Weights are effective balances read from the justified state.

```python
def get_attestation_weight(store: Store, validator_index: ValidatorIndex) -> Gwei:
    state = store.block_states[store.justified_root]
    return state.validators[validator_index].effective_balance
```

#### New `get_window_rounds`

The votes read in round `r` are those of the rounds
`max(0, r - SG_EXPIRY_WINDOW) <= k < r`; round `0` reads nothing.

```python
def get_window_rounds(round: Round) -> list[Round]:
    if round == 0:
        return []
    start = Round(0) if round < SG_EXPIRY_WINDOW else Round(round - SG_EXPIRY_WINDOW)
    return [Round(k) for k in range(start, round)]
```

#### New `get_resolved_votes`

Only votes for the finalized chain resolve for the grades: a vote for a block
conflicting with the finalized chain neither supports nor covers.

```python
def get_resolved_votes(
    store: Store, round: Round, cutoff_ms: Uint64, validator_index: ValidatorIndex
) -> list[AttestationRecord]:
    resolved = []
    for k in get_window_rounds(round):
        for record in store.attestation_pool.get(k, []):
            if record.validator_index != validator_index:
                continue
            if get_attestation_resolution_time_ms(store, record) >= cutoff_ms:
                continue
            safe_root = record.stabilization.safe_root
            if safe_root != Root() and not is_compatible(store, safe_root, store.finalized_root):
                continue
            resolved.append(record)
    return resolved
```

#### New `covers`

A vote covers `B` when its safe block `C` satisfies `B <= C`; an empty safe
value covers no block.

```python
def covers(store: Store, record: AttestationRecord, block_root: Root) -> bool:
    safe_root = record.stabilization.safe_root
    if safe_root == Root():
        return False
    return is_ancestor(store, block_root, safe_root)
```

#### New `equivocates_since`

```python
def equivocates_since(
    store: Store,
    round: Round,
    cutoff_ms: Uint64,
    validator_index: ValidatorIndex,
    from_round: Round,
) -> bool:
    for k in get_window_rounds(round):
        if k < from_round:
            continue
        safe_roots = set()
        for record in store.attestation_pool.get(k, []):
            if record.validator_index == validator_index and record.time_ms < cutoff_ms:
                safe_roots.add(record.stabilization.safe_root)
        if len(safe_roots) >= 2:
            return True
    return False
```

#### New `supports`

```python
def supports(
    store: Store,
    round: Round,
    early_ms: Uint64,
    late_ms: Uint64,
    validator_index: ValidatorIndex,
    block_root: Root,
) -> bool:
    early_votes = get_resolved_votes(store, round, early_ms, validator_index)
    late_votes = get_resolved_votes(store, round, late_ms, validator_index)
    if len(early_votes) == 0:
        return False
    latest = early_votes[0]
    for record in early_votes[1:]:
        key = (record.stabilization.round, record.stabilization.safe_root)
        if key > (latest.stabilization.round, latest.stabilization.safe_root):
            latest = record
    if not covers(store, latest, block_root):
        return False
    if equivocates_since(store, round, late_ms, validator_index, latest.stabilization.round):
        return False
    for record in late_votes:
        if record.stabilization.round > latest.stabilization.round and not covers(
            store, record, block_root
        ):
            return False
    return True
```

#### New `opposes`

```python
def opposes(
    store: Store,
    round: Round,
    early_ms: Uint64,
    late_ms: Uint64,
    validator_index: ValidatorIndex,
    block_root: Root,
) -> bool:
    early_votes = get_resolved_votes(store, round, early_ms, validator_index)
    late_votes = get_resolved_votes(store, round, late_ms, validator_index)
    latest_early_round = Round(0)
    for record in early_votes:
        latest_early_round = max(latest_early_round, record.stabilization.round)
    for record in late_votes:
        if record.stabilization.round >= latest_early_round and not covers(
            store, record, block_root
        ):
            return True
    return equivocates_since(store, round, late_ms, validator_index, latest_early_round)
```

#### New `get_window_validators`

```python
def get_window_validators(store: Store, round: Round) -> set[ValidatorIndex]:
    validators = set()
    for k in get_window_rounds(round):
        for record in store.attestation_pool.get(k, []):
            validators.add(record.validator_index)
    return validators
```

#### New `holds_relative_majority`

There is no absolute threshold: only the latest votes in the window are weighed,
the supporters of `B` against the validators that have moved away from it or
equivocated. The blocks holding a relative majority at one store and one cutoff
pair lie on one chain.

```python
def holds_relative_majority(
    store: Store, round: Round, early_ms: Uint64, late_ms: Uint64, block_root: Root
) -> bool:
    support_weight = Gwei(0)
    oppose_weight = Gwei(0)
    for validator_index in get_window_validators(store, round):
        if supports(store, round, early_ms, late_ms, validator_index, block_root):
            support_weight += get_attestation_weight(store, validator_index)
        elif opposes(store, round, early_ms, late_ms, validator_index, block_root):
            oppose_weight += get_attestation_weight(store, validator_index)
    return support_weight > oppose_weight
```

#### New `get_graded_block`

```python
def get_graded_block(
    store: Store, round: Round, early_ms: Uint64, late_ms: Uint64
) -> Root | None:
    graded = [
        root
        for root in store.blocks
        if holds_relative_majority(store, round, early_ms, late_ms, root)
    ]
    return get_deepest(store, graded)
```

#### New `update_grades`

The three grades of round `r` are the relative majority taken at the three
cutoff pairs of the schedule. Each field is written once per round, at its
completion time, and never recomputed; the grade-2 write falls in the last
interval of the previous round, so the fields always hold the current round's
grades when read.

```python
def update_grades(store: Store, time_ms: Uint64) -> None:
    delta = get_delta_ms()
    slot = compute_slot_at_time_ms(store.genesis_time_ms, time_ms)
    round = compute_round_at_slot(slot)
    next_round_start = compute_round_start_ms(store, Round(round + 1))
    round_start = compute_round_start_ms(store, round)
    if time_ms == next_round_start - delta:
        store.grade_2_root = get_graded_block(
            store, Round(round + 1), Uint64(next_round_start - 5 * delta), Uint64(next_round_start - delta)
        )
    elif time_ms == round_start:
        store.grade_1_root = get_graded_block(
            store, round, Uint64(round_start - 4 * delta), Uint64(round_start - 2 * delta)
        )
    elif time_ms == round_start + delta:
        store.grade_0_root = get_graded_block(
            store, round, Uint64(round_start - 3 * delta), Uint64(round_start - 3 * delta)
        )
```

#### New `get_active_prefix`

A saved block is active when it has an ancestor in the filtered block tree, and
its active prefix is the deepest such ancestor: the fork choice can use it, and
it descends the FG root.

```python
def get_active_prefix(store: Store, graded_root: Root | None) -> Root | None:
    if graded_root is None:
        return None
    tree_roots = get_filtered_block_tree(store)
    prefixes = [root for root in tree_roots if is_ancestor(store, root, graded_root)]
    return get_deepest(store, prefixes)
```

#### New `is_grade_0_compatible`

Grade 0 is used only negatively, as a veto. The veto is not restricted to the
filtered tree, since a fresh majority against the confirmed branch counts
whatever the position of its own block.

```python
def is_grade_0_compatible(store: Store, block_root: Root) -> bool:
    if store.grade_0_root is None:
        return True
    return is_compatible(store, block_root, store.grade_0_root)
```

#### New `get_sg_root`

The SG root is the active prefix of the saved grade-1 block, and the FG root
when there is no grade-1 block or it has no active prefix.

```python
def get_sg_root(store: Store) -> Root:
    active = get_active_prefix(store, store.grade_1_root)
    if active is None:
        return get_fg_root(store)
    return active
```

### Head

#### New `get_head_in_tree`

```python
def get_head_in_tree(
    store: Store,
    tree_roots: list[Root],
    vote_slot: Slot,
    votes: list[GoldfishVoteRecord],
    support_votes: list[GoldfishVoteRecord],
) -> Root:
    anchor_root = get_sg_root(store)
    committee = get_goldfish_committee_for(store, vote_slot)
    return goldfish_fork_choice(store, anchor_root, tree_roots, committee, votes, support_votes)
```

#### New `get_head_with_votes`

```python
def get_head_with_votes(
    store: Store,
    vote_slot: Slot,
    votes: list[GoldfishVoteRecord],
    support_votes: list[GoldfishVoteRecord],
) -> Root:
    tree_roots = get_filtered_block_tree(store)
    return get_head_in_tree(store, tree_roots, vote_slot, votes, support_votes)
```

#### New `get_head`

The generic head reads the current slot's votes with their resolved subset, as
the attestation duty does. The proposer instead reads the previous slot's votes;
see the validator document.

```python
def get_head(store: Store) -> Root:
    vote_slot = get_current_slot(store)
    votes = store.goldfish_votes.get(vote_slot, [])
    support_votes = [
        record
        for record in votes
        if get_goldfish_resolution_time_ms(store, record) < TIME_MS_INFINITY
    ]
    return get_head_with_votes(store, vote_slot, votes, support_votes)
```

### Confirmation

#### New `advance_record`

No candidate or an ancestor leaves the record unchanged; an extension or a
conflicting candidate replaces it. This permits recovery from a conflicting
record formed in an unsafe period.

```python
def advance_record(store: Store, old_root: Root, candidate_root: Root | None) -> Root:
    if candidate_root is None or is_ancestor(store, candidate_root, old_root):
        return old_root
    return candidate_root
```

#### New `get_stable_root_candidate`

```python
def get_stable_root_candidate(store: Store) -> Root:
    active = get_active_prefix(store, store.grade_2_root)
    if active is not None:
        return active
    return get_fg_root(store)
```

#### New `update_user_confirmation_records`

The confirmation record's write is floored on the stable record, in the same
duty and after it: the candidate is recorded when it extends the new stable
record; the old record is kept while it still extends the new stable record; and
only when the stable record has left the old record's chain does the
confirmation record move to the stable record itself. By these three cases alone
the records are ordered at every node and every time, and the floor cannot undo
the record's own progress.

```python
def update_user_confirmation_records(store: Store, candidate_root: Root | None) -> None:
    confirmed = advance_record(store, store.latest_confirmed_root, candidate_root)
    store.latest_stable_root = advance_record(
        store, store.latest_stable_root, get_stable_root_candidate(store)
    )
    if is_ancestor(store, store.latest_stable_root, confirmed):
        store.latest_confirmed_root = confirmed
    elif not is_ancestor(store, store.latest_stable_root, store.latest_confirmed_root):
        store.latest_confirmed_root = store.latest_stable_root
```

#### New `update_confirmation`

Runs at six intervals after the start of slot `slot`, which is two intervals
into the following slot. The protocol-facing value `live_confirmed_root`
advances only when the walk's result itself holds a window majority, and
otherwise returns the FG root, which sits below every walk floor in the
attestation duty.

```python
def update_confirmation(store: Store, slot: Slot) -> None:
    delta = get_delta_ms()
    slot_start = compute_slot_start_ms(store, slot)
    all_votes = store.goldfish_votes.get(slot, [])
    early_votes = [
        record
        for record in all_votes
        if get_goldfish_resolution_time_ms(store, record) < slot_start + 2 * delta
    ]
    late_votes = [record for record in all_votes if record.time_ms < slot_start + 6 * delta]
    support_votes = []
    for record in early_votes:
        distinct = [
            other
            for other in late_votes
            if other.validator_index == record.validator_index
            and other.head_root != record.head_root
        ]
        if len(distinct) == 0:
            support_votes.append(record)
    committee = get_goldfish_committee_for(store, slot)
    voters_count = count_goldfish_voters(committee, late_votes)

    tree_roots = get_filtered_block_tree(store)
    fg_root = get_fg_root(store)
    anchor_root = get_sg_root(store)

    # GHOST walk with the strict-majority eligibility
    head = anchor_root
    while True:
        eligible_children = []
        for child in get_children(store, tree_roots, head):
            score = get_goldfish_score(store, committee, support_votes, support_votes, child)
            if 2 * score > voters_count:
                eligible_children.append(child)
        if len(eligible_children) == 0:
            break
        best = eligible_children[0]
        best_score = get_goldfish_score(store, committee, support_votes, support_votes, best)
        for child in eligible_children[1:]:
            score = get_goldfish_score(store, committee, support_votes, support_votes, child)
            if (score, child) > (best_score, best):
                best = child
                best_score = score
        head = best

    head_score = get_goldfish_score(store, committee, support_votes, support_votes, head)
    if 2 * head_score > voters_count:
        store.live_confirmed_root = head
        candidate: Root | None = head
    else:
        store.live_confirmed_root = fg_root
        # The saved grade-2 block stands in for the walk
        candidate = get_active_prefix(store, store.grade_2_root)
    update_user_confirmation_records(store, candidate)
```

#### New `get_stable`

```python
def get_stable(store: Store) -> Root:
    """
    Return the stable chain tip. User-facing; no protocol rule reads it.
    """
    if is_ancestor(store, store.finalized_root, store.latest_stable_root):
        return store.latest_stable_root
    return store.finalized_root
```

#### New `get_confirmed`

```python
def get_confirmed(store: Store) -> Root:
    """
    Return the available chain tip. User-facing; no protocol rule reads
    it.
    """
    stable_root = get_stable(store)
    if is_ancestor(store, stable_root, store.latest_confirmed_root):
        return store.latest_confirmed_root
    return stable_root
```

### Payload status

#### New `get_payload_status_in_chain`

Every block below a chain's tip has its payload status committed by its child on
that chain. Only the tip itself is pending: it is in exactly the position of
today's head, whose payload decision the next proposer makes. A user reading one
of the three tips derives the statuses of the chain below it with this accessor.

```python
def get_payload_status_in_chain(store: Store, root: Root, descendant_root: Root) -> PayloadStatus:
    """
    Return the payload status of ``root`` as committed on the chain to
    ``descendant_root``.
    """
    assert is_ancestor(store, root, descendant_root)
    if root == descendant_root:
        return PAYLOAD_STATUS_PENDING
    child_root = descendant_root
    while store.blocks[child_root].parent_root != root:
        child_root = store.blocks[child_root].parent_root
    return get_parent_payload_status(store, store.blocks[child_root])
```

#### Modified `should_build_on_full`

*Note*: Redefined over a block root rather than a `ForkChoiceNode`. The proposer
commits the head's payload status in its bid; Trident never weighs full against
empty by votes. For a previous-slot head, the PTC view on timeliness and data
availability is considered; for an older head (after skipped slots), local
payload verification decides, since no votes carry a payload bit to consult.

```python
def should_build_on_full(store: Store, head_root: Root) -> bool:
    if not is_payload_verified(store, head_root):
        return False
    if store.blocks[head_root].slot + 1 == get_current_slot(store):
        if payload_timeliness(store, head_root, timely=False):
            return False
        if payload_data_availability(store, head_root, available=False):
            return False
    return True
```

## Handlers

### New `update_finality`

The justified pair tracks the lex-greatest justification event compatible with
the finalized block. The finalized block advances only to a viable proper
descendant of itself below the justified block, so finalization never reverts. A
finality advance cuts every saved grade back to its deepest ancestor compatible
with the new finalized block.

```python
def update_finality(store: Store, state: BeaconState) -> None:
    store.max_height = max(store.max_height, state.height)
    justified = state.latest_justified
    if is_ancestor(store, store.finalized_root, justified.root) and (
        justified.height,
        justified.root,
    ) > (store.justified_height, store.justified_root):
        store.justified_root = justified.root
        store.justified_height = justified.height
    finalized = state.latest_finalized
    if (
        finalized.root != store.finalized_root
        and is_ancestor(store, store.finalized_root, finalized.root)
        and is_ancestor(store, finalized.root, store.justified_root)
        and finalized.root in get_viable_blocks(store)
    ):
        store.finalized_root = finalized.root
        store.grade_2_root = cut_to_compatible(store, store.grade_2_root)
        store.grade_1_root = cut_to_compatible(store, store.grade_1_root)
        store.grade_0_root = cut_to_compatible(store, store.grade_0_root)
```

### New `cut_to_compatible`

```python
def cut_to_compatible(store: Store, graded_root: Root | None) -> Root | None:
    if graded_root is None:
        return None
    if is_compatible(store, graded_root, store.finalized_root):
        return graded_root
    ancestors = [
        root
        for root in store.blocks
        if is_ancestor(store, root, graded_root)
        and is_compatible(store, root, store.finalized_root)
    ]
    return get_deepest(store, ancestors)
```

### New `on_goldfish_vote`

Run `on_goldfish_vote(store, vote)` on receiving a Goldfish vote from the wire,
after gossip validation, and for every vote carried by an accepted block. The
node ignores votes older than the previous slot or from a future slot, and keeps
at most two distinct votes per validator and slot, which is all any rule reads.

```python
def on_goldfish_vote(store: Store, validator_index: ValidatorIndex, data: GoldfishVoteData) -> None:
    current_slot = get_current_slot(store)
    if data.slot + 1 < current_slot or data.slot > current_slot:
        return
    records = store.goldfish_votes.get(data.slot, [])
    held = [record for record in records if record.validator_index == validator_index]
    for record in held:
        if record.head_root == data.beacon_block_root:
            return
    if len(held) >= 2:
        return
    records.append(
        GoldfishVoteRecord(
            validator_index=validator_index,
            slot=data.slot,
            head_root=data.beacon_block_root,
            time_ms=store.time_ms,
        )
    )
    store.goldfish_votes[data.slot] = records
```

### New `on_trident_attestation`

Run on receiving an attestation from the wire, after gossip validation, and for
every attestation row carried by an accepted block's stabilization aggregates
(with `finality=None` when the block carries only the stabilization component).
The pool keeps at most two attestations with distinct safe blocks per validator
and round, and attestations differing only in their finality component are one
vote, so the second of them is refused.

```python
def on_trident_attestation(
    store: Store,
    validator_index: ValidatorIndex,
    stabilization: StabilizationData,
    finality: FinalityData | None,
) -> None:
    current_round = get_current_round(store)
    min_round = Round(0) if current_round < SG_EXPIRY_WINDOW else Round(
        current_round - SG_EXPIRY_WINDOW
    )
    if stabilization.round < min_round or stabilization.round > current_round:
        return
    records = store.attestation_pool.get(stabilization.round, [])
    held_safe_roots = set()
    for record in records:
        if record.validator_index == validator_index:
            held_safe_roots.add(record.stabilization.safe_root)
    if stabilization.safe_root in held_safe_roots or len(held_safe_roots) >= 2:
        return
    records.append(
        AttestationRecord(
            validator_index=validator_index,
            stabilization=stabilization,
            finality=finality,
            time_ms=store.time_ms,
        )
    )
    store.attestation_pool[stabilization.round] = records
```

### New `on_block`

A block is accepted only when its parent is held, it descends the finalized
block, and every attestation it includes has a round at most the round of the
block's slot: a block may not include attestations from its own future. A block
that builds on its parent's full payload is accepted only when that payload has
been verified by `on_execution_payload_envelope`. A call that returns before
acceptance does not consume the block: a later delivery (of the block, or of the
awaited payload envelope) may invoke the handler again after the guard condition
changes. An accepted block's attestation rows pass through
`on_trident_attestation` after the block's finality update, under the same
admission rule as a wire receipt.

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    block = signed_block.message
    block_root = hash_tree_root(block)
    if block.slot > get_current_slot(store):
        return
    if block_root in store.blocks:
        return
    if block.parent_root not in store.blocks:
        return
    if not is_ancestor(store, store.finalized_root, block.parent_root):
        return
    # A commitment to the parent's full payload needs the verified envelope
    if is_parent_node_full(store, block) and not is_payload_verified(store, block.parent_root):
        return
    block_round = compute_round_at_slot(block.slot)
    for aggregate in block.body.stabilization_aggregates:
        if aggregate.data.round > block_round:
            return
    for aggregate in block.body.finality_aggregates:
        if aggregate.data.round > block_round:
            return

    state = store.block_states[block.parent_root].copy()
    state_transition(state, signed_block, True)

    store.blocks[block_root] = block.copy()
    store.block_states[block_root] = state
    store.block_times_ms[block_root] = store.time_ms

    # Open the block's PTC voting and fold the carried PTC messages
    store.payload_timeliness_vote[block_root] = [None] * PTC_SIZE
    store.payload_data_availability_vote[block_root] = [None] * PTC_SIZE
    notify_ptc_messages(store, state, block.body.payload_attestations)

    # Process the carried Goldfish votes
    for included in block.body.goldfish_votes:
        committee = get_goldfish_committee_for(store, included.aggregate.data.slot)
        for i in range(len(committee)):
            if included.aggregate.aggregation_bits[i]:
                on_goldfish_vote(store, committee[i], included.aggregate.data)

    update_finality(store, state)

    # Process the carried attestation rows after the finality update
    for aggregate in block.body.stabilization_aggregates:
        members = get_round_subnet_members(state, aggregate.data.round, aggregate.subnet_id)
        for i in range(len(members)):
            if aggregate.aggregation_bits[i]:
                on_trident_attestation(store, members[i], aggregate.data, None)
```

### New `on_tick`

Run `on_tick(store, time_ms)` whenever `time_ms > store.time_ms`. The public
times of the schedule are the only tick times. A tick first completes the grades
whose completion time it is, from the store as it stands, and only then advances
the clock; an object processed between two public times gets the earlier one's
stamp. The slot-`(s-1)` confirmation evaluation runs two intervals into slot
`s`.

```python
def on_tick(store: Store, time_ms: Uint64) -> None:
    delta = get_delta_ms()
    next_public_time = Uint64((store.time_ms // delta + 1) * delta)
    while next_public_time <= time_ms:
        update_grades(store, next_public_time)
        store.time_ms = next_public_time
        slot = get_current_slot(store)
        slot_start = compute_slot_start_ms(store, slot)
        if slot > 0 and next_public_time == slot_start + 2 * delta:
            update_confirmation(store, Slot(slot - 1))
        next_public_time = Uint64(next_public_time + delta)
    store.time_ms = max(store.time_ms, time_ms)
```
