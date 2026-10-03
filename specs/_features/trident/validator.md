# Trident -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Duty schedule](#duty-schedule)
- [Helpers](#helpers)
  - [`AntiSlashingRecord`](#antislashingrecord)
  - [New `get_finality_vote`](#new-get_finality_vote)
  - [New `get_height_vote`](#new-get_height_vote)
  - [New `record_attestation`](#new-record_attestation)
  - [New `get_safe_block_root`](#new-get_safe_block_root)
  - [New `get_finality_vote_source`](#new-get_finality_vote_source)
- [Duties](#duties)
  - [Block proposal](#block-proposal)
  - [Goldfish vote](#goldfish-vote)
  - [Attestation](#attestation)
  - [Aggregation](#aggregation)

<!-- mdformat-toc end -->

## Introduction

This document describes the duties of an honest validator under Trident. The FFG
attestation, aggregation, and attester-slashing duties are replaced; the
proposer, sync-committee, and builder duties are retained with the modifications
below.

An honest validator emits at most one proposal per slot, one Goldfish vote per
slot, and one combined attestation per round.

## Duty schedule

All times are offsets from the slot start, in units of `DELTA_MS`.

| Time                                               | Duty                                          |
| -------------------------------------------------- | --------------------------------------------- |
| `0`                                                | Proposal (the slot's proposer)                |
| `1 * DELTA_MS`                                     | Goldfish vote (the slot's Goldfish committee) |
| `6 * DELTA_MS` past the round's opening slot start | Attestation (every validator, once per round) |

The support cutoff (`2 * DELTA_MS`) and the view freeze (`3 * DELTA_MS`) are
store events, not duties. The attestation time `a_r` falls two intervals into
the second slot of round `r`, after that slot's confirmation evaluation in the
same tick; all three grades of round `r` are complete by then.

## Helpers

### `AntiSlashingRecord`

The validator keeps an anti-slashing record, one entry per height: its first
target, whether it emitted a timeout, and the target of its first finality vote.
It belongs to the validator client, not to the store, and `record_attestation`
is its only writer. This is modeled after the slashing protection database of
today's validators: a minimal, hardened component separate from the beacon node.

```python
@dataclass
class AntiSlashingRecord:
    targets: dict[Height, Root] = field(default_factory=dict)
    timeout_heights: set[Height] = field(default_factory=set)
    locks: dict[Height, Root] = field(default_factory=dict)
```

### New `get_finality_vote`

A finality vote is emitted for a justification not yet finalized, when the
record allows it: no conflicting first target, no timeout, and no conflicting
lock at its height.

```python
def get_finality_vote(
    record: AntiSlashingRecord, justified: HeightCheckpoint, finalized_height: Height
) -> FinalityVote:
    if justified.height > finalized_height:
        target = record.targets.get(justified.height)
        lock = record.locks.get(justified.height)
        if (
            (target is None or target == justified.root)
            and justified.height not in record.timeout_heights
            and (lock is None or lock == justified.root)
        ):
            return FinalityVote(height=justified.height, target_root=justified.root)
    return FinalityVote(height=Height(0), target_root=Root())
```

### New `get_height_vote`

The rules, in order: a timeout repeats, naming the current entry; a lock
repeats, and locked elsewhere means waiting out the height; a recorded target
repeats; with no history, adopt the chain's target unless the height is
non-justifiable; otherwise time out. The attestation's own finality vote acts as
the lock at its height, so one attestation never forms E1 evidence against
itself.

```python
def get_height_vote(
    record: AntiSlashingRecord,
    source_height: Height,
    source_entry_root: Root,
    source_non_justifiable: bool,
    finality_vote: FinalityVote,
) -> HeightVote:
    if source_height == 0:
        return HeightVote(height=Height(0), entry_root=Root(), is_timeout=Boolean(False))
    lock = record.locks.get(source_height)
    if not is_empty_finality_vote(finality_vote) and finality_vote.height == source_height:
        lock = finality_vote.target_root
    if source_height in record.timeout_heights:
        return HeightVote(
            height=source_height, entry_root=source_entry_root, is_timeout=Boolean(True)
        )
    if lock is not None:
        if lock == source_entry_root:
            return HeightVote(
                height=source_height, entry_root=source_entry_root, is_timeout=Boolean(False)
            )
        # Locked elsewhere: wait out the height
        return HeightVote(height=Height(0), entry_root=Root(), is_timeout=Boolean(False))
    target = record.targets.get(source_height)
    if target is not None:
        if target == source_entry_root:
            return HeightVote(
                height=source_height, entry_root=source_entry_root, is_timeout=Boolean(False)
            )
    elif not source_non_justifiable:
        # No history: adopt the chain's target
        return HeightVote(
            height=source_height, entry_root=source_entry_root, is_timeout=Boolean(False)
        )
    return HeightVote(
        height=source_height, entry_root=source_entry_root, is_timeout=Boolean(True)
    )
```

### New `record_attestation`

```python
def record_attestation(record: AntiSlashingRecord, data: FinalityData) -> None:
    if not is_empty_finality_vote(data.finality_vote):
        record.locks[data.finality_vote.height] = data.finality_vote.target_root
    if not is_empty_height_vote(data.height_vote):
        height_vote = data.height_vote
        if not height_vote.is_timeout and record.targets.get(height_vote.height) is None:
            record.targets[height_vote.height] = height_vote.entry_root
        if height_vote.is_timeout:
            record.timeout_heights.add(height_vote.height)
```

### New `get_safe_block_root`

The safe block is the deepest grade-0-compatible block between the SG root and
the confirmed value. The grade-2 block stays canonical as the first fallback;
the anchor fallback keeps voting total.

```python
def get_safe_block_root(store: Store, active_grade_2_root: Root | None) -> Root:
    confirmed_root = store.live_confirmed_root
    anchor_root = get_sg_root(store)
    candidates = []
    root = confirmed_root
    while is_ancestor(store, anchor_root, root):
        if is_grade_0_compatible(store, root):
            candidates.append(root)
        if root == anchor_root:
            break
        root = store.blocks[root].parent_root
    deepest = get_deepest(store, candidates)
    if deepest is not None:
        return deepest
    if active_grade_2_root is not None:
        return active_grade_2_root
    if store.grade_2_root is not None:
        # Grade 2 exists, but the root has passed it
        return get_fg_root(store)
    return anchor_root
```

### New `get_finality_vote_source`

The height vote is built from a confirmed block's height fields: a target vote
can create a justification, and only confirmed blocks may be justified. The
finality vote is built from the head's finality fields: its subject is already
justified, so it may read an unconfirmed chain, and the head chain state holds
the freshest justification. With no fresh quorum (no active grade-2 block), no
height vote is emitted.

```python
def get_finality_vote_source(
    store: Store, active_grade_2_root: Root | None
) -> tuple[Height, Root, bool, HeightCheckpoint, Height]:
    head_root = get_head(store)
    head_state = store.block_states[head_root]
    justified = head_state.latest_justified
    finalized_height = head_state.latest_finalized.height
    if active_grade_2_root is None:
        return (Height(0), Root(), False, justified, finalized_height)
    confirmed_root = store.live_confirmed_root
    candidates = []
    root = confirmed_root
    while is_ancestor(store, active_grade_2_root, root):
        if is_grade_0_compatible(store, root):
            candidates.append(root)
        if root == active_grade_2_root:
            break
        root = store.blocks[root].parent_root
    source_root = get_deepest(store, candidates)
    if source_root is None:
        source_root = active_grade_2_root
    source_state = store.block_states[source_root]
    return (
        source_state.height,
        source_state.height_entry_root,
        bool(source_state.non_justifiable),
        justified,
        finalized_height,
    )
```

## Duties

### Block proposal

The proposer runs at the slot start. Beyond the inherited assembly (bid, randao,
operations), the proposer:

0. Decides whether to build on the full or the empty version of its head with
   `should_build_on_full(store, head_root)` and commits the choice in its bid's
   `parent_block_hash`. This commitment is what fixes the parent's payload
   status on this branch; no vote weighs full against empty.

1. Computes the head with the ordinary full-tree fork choice over every
   previous-slot Goldfish vote it holds, with the resolved subset as support:

```python
def get_proposer_head(store: Store, slot: Slot) -> Root:
    votes = store.goldfish_votes.get(Slot(slot - 1), [])
    support_votes = [
        record
        for record in votes
        if get_goldfish_resolution_time_ms(store, record) < TIME_MS_INFINITY
    ]
    return get_head_with_votes(store, Slot(slot - 1), votes, support_votes)
```

2. Includes every previous-slot Goldfish vote it holds, aggregated by
   `(slot, beacon_block_root)` class over the committee bits, and marks in
   `support_bits` exactly the votes resolved at proposal time. The proposer does
   not apply the view freeze; voters do not derive the support subset again from
   their later stores.

3. Includes the attestations of its pool whose round lies in the inclusive
   window `[max(0, r - SG_EXPIRY_WINDOW), r]` of the current round `r`, together
   with the attestations included in held blocks of a slot in that window (again
   those with a round in the window), removing every attestation already on the
   parent's chain, with at most two attestations of each validator for each
   round. Unresolved attestations are included too: resolution is a fact of the
   proposer's store, not of the attestation.

*Note*: Under the block caps, the proposer MUST prefer, in order: finality
aggregates carrying votes that advance the current height's quorums; then
stabilization aggregates of more recent rounds; then older window rounds. The
selection within one priority class is by descending participant count. This
deterministic priority replaces the unspecified choice in the model, whose cap
(two rows per validator and round) bounds honest proposals only.

### Goldfish vote

A member of the slot-`s` Goldfish committee votes one interval into the slot.
The vote duty uses a block-domain merge analogous to its vote merge: it forms a
processed-block view from blocks received before the previous slot's freeze and
every ancestor of a current-slot proposal, then recomputes viability and the
filtered block tree inside that view. A late witness cannot make an old
pre-freeze child enter this vote's walk.

```python
def get_goldfish_vote_head(store: Store, slot: Slot) -> Root:
    delta = get_delta_ms()
    freeze_ms = Uint64(compute_slot_start_ms(store, Slot(slot - 1)) + 3 * delta)
    # Votes received before the freeze
    votes = [
        record
        for record in store.goldfish_votes.get(Slot(slot - 1), [])
        if record.time_ms < freeze_ms
    ]
    support_votes = [
        record
        for record in votes
        if get_goldfish_resolution_time_ms(store, record) < freeze_ms
    ]
    # Merge the views carried by current-slot proposals
    for block in store.blocks.values():
        if block.slot != slot:
            continue
        for included in block.body.goldfish_votes:
            if included.aggregate.data.slot + 1 != slot:
                continue
            committee = get_goldfish_committee_for(store, included.aggregate.data.slot)
            for i in range(len(committee)):
                if not included.aggregate.aggregation_bits[i]:
                    continue
                carried = GoldfishVoteRecord(
                    validator_index=committee[i],
                    slot=included.aggregate.data.slot,
                    head_root=included.aggregate.data.beacon_block_root,
                    time_ms=store.time_ms,
                )
                votes.append(carried)
                if (
                    included.support_bits[i]
                    and included.aggregate.data.beacon_block_root in store.blocks
                ):
                    support_votes.append(carried)
    # The voter's processed-block view
    proposal_roots = [root for root, block in store.blocks.items() if block.slot == slot]
    view = []
    for root in store.blocks:
        if store.block_times_ms[root] < freeze_ms:
            view.append(root)
            continue
        for proposal_root in proposal_roots:
            if is_ancestor(store, root, proposal_root):
                view.append(root)
                break
    tree_roots = get_filtered_block_tree_from(store, view)
    return get_head_in_tree(store, tree_roots, Slot(slot - 1), votes, support_votes)
```

The validator signs `GoldfishVoteData(slot=slot, beacon_block_root=head)` with
`DOMAIN_GOLDFISH_VOTE`, broadcasts the `GoldfishVote`, and processes it into its
own store.

### Attestation

Every validator attests once per round, at `a_r`, six intervals after the
round's opening slot start. The beacon node derives the safe block, the source
fields, and the head's finality fields from the store; the validator client
applies the anti-slashing rules and signs. The record is updated before the
attestation is released.

```python
def produce_attestation(
    store: Store, record: AntiSlashingRecord, validator_index: ValidatorIndex, round: Round
) -> TridentAttestation:
    active_grade_2_root = get_active_prefix(store, store.grade_2_root)
    safe_root = get_safe_block_root(store, active_grade_2_root)
    (
        source_height,
        source_entry_root,
        source_non_justifiable,
        justified,
        finalized_height,
    ) = get_finality_vote_source(store, active_grade_2_root)
    finality_vote = get_finality_vote(record, justified, finalized_height)
    height_vote = get_height_vote(
        record, source_height, source_entry_root, source_non_justifiable, finality_vote
    )
    stabilization = StabilizationData(round=round, safe_root=safe_root)
    finality = FinalityData(round=round, height_vote=height_vote, finality_vote=finality_vote)
    # Record, then release
    record_attestation(record, finality)
    return TridentAttestation(
        validator_index=validator_index,
        stabilization=stabilization,
        finality=finality,
        stabilization_signature=BLSSignature(),
        finality_signature=BLSSignature(),
    )
```

The two components are signed separately: `stabilization` with
`DOMAIN_STABILIZATION_VOTE` and `finality` with `DOMAIN_FINALITY_VOTE`, both at
the epoch of the round's opening slot. The validator broadcasts the attestation
on its round subnet (`validator_index % ROUND_SUBNET_COUNT`) and processes it
into its own store.

*Note*: Implementations SHOULD batch-verify the two same-signer signatures of a
received attestation with one random linear combination, which costs the same
two pairings as a single verification.

### Aggregation

Per round and subnet, designated aggregators collect the attestations of their
subnet and publish one `StabilizationAggregate` per distinct `StabilizationData`
and one `FinalityAggregate` per distinct `FinalityData`, over the subnet's
member bits. Under synchrony honest validators converge on few classes; the two
components aggregate independently, so divergence in one does not fragment the
other. Aggregator selection follows the inherited sync-committee aggregator
pattern and is not further specified here.

For Goldfish votes, a validator occupying `k` committee seats broadcasts a
single `GoldfishVote`; the aggregator sets the validator's `k` seat bits and
adds the one received signature `k` times to the aggregate, so that verification
against the `k` repeated pubkeys succeeds. This follows the payload timeliness
committee's duplicate-index convention.

*Note*: No proved invariant couples a validator's two attestation components:
the nesting of the three tips is premise-free, accountable safety and the leak
read only the finality component, and the delivery premises of the verified
model cover wire broadcast and relay, not block carriage. A block may therefore
count a validator's finality component while its stabilization component is
omitted. Block carriage of stabilization rows remains the recovery backstop for
refilling pools, so when including a round's finality aggregates under space
pressure, the proposer SHOULD also include that round's stabilization aggregates
when space permits. This is guidance, not a validity condition: linking the two
would reintroduce the fragmentation coupling that independent aggregation exists
to break.
