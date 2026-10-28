# EIP-8453 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
  - [New `FinalitySigningRecord`](#new-finalitysigningrecord)
- [Validator assignments](#validator-assignments)
  - [Attestation committees](#attestation-committees)
  - [Head vote committees](#head-vote-committees)
  - [Lookahead](#lookahead)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Preparing for a `BeaconBlock`](#preparing-for-a-beaconblock)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Head votes](#head-votes)
      - [Safe votes](#safe-votes)
      - [Attestations](#attestations)
      - [Attester slashings](#attester-slashings)
  - [Head voting](#head-voting)
    - [Head vote data](#head-vote-data)
    - [Construct head vote](#construct-head-vote)
    - [Broadcast head vote](#broadcast-head-vote)
  - [Safe voting](#safe-voting)
    - [Safe vote assignment](#safe-vote-assignment)
    - [Safe vote data](#safe-vote-data)
    - [Construct safe vote](#construct-safe-vote)
    - [Broadcast safe vote](#broadcast-safe-vote)
  - [Attesting](#attesting)
    - [Attestation data](#attestation-data)
      - [Finality pair](#finality-pair)
      - [Height pair](#height-pair)
      - [Construct data](#construct-data)
      - [Record attestation](#record-attestation)
    - [Construct attestation](#construct-attestation)
    - [Broadcast attestation](#broadcast-attestation)
  - [Attestation aggregation](#attestation-aggregation)
    - [Aggregation selection](#aggregation-selection)
      - [Head vote aggregation selection](#head-vote-aggregation-selection)
      - [Safe vote aggregation selection](#safe-vote-aggregation-selection)
      - [FG attestation aggregation selection](#fg-attestation-aggregation-selection)
    - [Construct aggregate](#construct-aggregate)
      - [Head votes](#head-votes-1)
      - [Safe vote aggregation](#safe-vote-aggregation)
      - [FG attestations](#fg-attestations)
      - [Aggregation bits](#aggregation-bits)
    - [Aggregate wrappers](#aggregate-wrappers)
      - [New `HeadVoteAggregateAndProof`](#new-headvoteaggregateandproof)
      - [New `SignedHeadVoteAggregateAndProof`](#new-signedheadvoteaggregateandproof)
      - [New `SafeVoteAggregateAndProof`](#new-safevoteaggregateandproof)
      - [New `SignedSafeVoteAggregateAndProof`](#new-signedsafevoteaggregateandproof)
    - [Broadcast aggregate](#broadcast-aggregate)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8453.

EIP-8453 replaces the combined LMD-GHOST and Casper FFG attestation with
separate head votes for the available chain (AC) and attestations for the
finality gadget (FG). Each epoch, every active validator sits on one attestation
committee and, in every round, casts its FG attestation in that committee's
slot. In every slot, a head vote committee casts head votes.

## Prerequisites

This document is an extension of the
[Heze -- Honest Validator](../../heze/validator.md) guide. All behaviors and
definitions in that document, and documents it extends, carry over unless
explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in
[EIP-8453 -- The Beacon Chain](./beacon-chain.md) are requisite for this
document and used throughout.

Each duty reads the [fork choice](./fork-choice.md) exactly once, at its
deadline:

| Duty           | Deadline                                                  | Fork-choice read                                 |
| -------------- | --------------------------------------------------------- | ------------------------------------------------ |
| Proposal       | start of the slot                                         | `get_head(store, Slot(slot - 1))`                |
| Head vote      | `get_head_vote_due_ms()` into the slot                    | `get_voter_head(store, slot)`                    |
| Safe vote      | `get_head_vote_due_ms()` into the assigned sub-round slot | `get_safe_vote_node(store)`                      |
| FG attestation | `get_attestation_due_ms()` into the committee's slot      | `get_fg_target_source`, `get_fg_finality_source` |

## Helpers

### New `FinalitySigningRecord`

The `FinalitySigningRecord` tracks a validator's FG signing history. A separate
record is maintained for each validator key, independently of whether its
attestations are included on chain.

```python
@dataclass
class FinalitySigningRecord:
    targets: dict[Height, Root]
    timeouts: set[Height]
    finality_locks: dict[Height, Root]
    entries: dict[Height, set[Root]]
```

The fields are initialized empty for a validator with no prior EIP-8453 signing
history:

- `targets[h]`: the first target voted for at height `h`.
- `timeouts`: heights at which a timeout was signed.
- `finality_locks[h]`: the block named by a finality vote at height `h`.
- `entries[h]`: entries named by any height vote at height `h`.

*Note*: The record persists across restarts. Finality signing locks do not
expire and are distinct from the temporary AC locks maintained by fork choice.

## Validator assignments

### Attestation committees

To determine its attestation committee for `epoch`, a validator calls
`get_attestation_committee_assignment(state, epoch, validator_index)`.

```python
def get_attestation_committee_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> CommitteeIndex | None:
    """
    Return the index of the validator's attestation committee in ``epoch``, if
    any.
    """
    for index in range(ATTESTATION_COMMITTEES_PER_ROUND):
        committee_index = CommitteeIndex(index)
        if validator_index in get_attestation_committee(state, epoch, committee_index):
            return committee_index
    return None
```

Every active validator sits on exactly one attestation committee per epoch. In
each round, it attests in the slot
`compute_attestation_committee_slot(round, committee_index)`, using the
committee of that slot's epoch. Round numbering is defined by
`compute_round_at_slot` and does not restart at the EIP-8453 fork.

### Head vote committees

To determine the slots in which it casts head votes, a validator calls
`get_head_vote_committee_assignments(state, epoch, validator_index)`.

```python
def get_head_vote_committee_assignments(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> Sequence[Slot]:
    """
    Return the slots of ``epoch`` in which the validator sits on the head vote
    committee.
    """
    assert epoch <= get_current_epoch(state) + 1

    slots: list[Slot] = []
    start_slot = compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        if validator_index in get_head_vote_committee(state, Slot(slot)):
            slots.append(Slot(slot))
    return slots
```

A validator can sit on the head vote committee in several slots of an epoch, or
in none. It casts one head vote per assigned slot, even if it holds several
seats in that slot's committee.

### Lookahead

Assignments are computed from the chain state using `get_attestation_committee`
and `get_head_vote_committee`. A validator should recompute its assignment when
the dependent chain state changes.

Assignments are read from the finalized chain, matching
[`get_head_vote_committee_at_slot`](./fork-choice.md#new-get_head_vote_committee_at_slot)
in the fork choice: the dependent root is the latest finalized block root, and
the state's `head_vote_committee_window` provides `MIN_SEED_LOOKAHEAD` epochs of
lookahead. A validator recomputes its assignments when the finalized block
changes. The exact dependent state remains under discussion; see the fork-choice
[divergence notes](./fork-choice.md#divergences-from-the-paper).

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Block and sidecar proposal

A validator is expected to propose a `SignedBeaconBlock` at the beginning of any
slot during which `is_proposer(state, validator_index)` returns `True`.

#### Preparing for a `BeaconBlock`

Let `parent` be the block returned by the AC proposal procedure, together with
its previous slot head-vote view.

The AC proposal procedure selects the parent at the start of the slot:

- Let `head = get_head(store, Slot(slot - 1))`: the walk over the previous
  slot's votes in the proposer's full view. The proposer applies no view freeze;
  it uses every previous-slot vote it holds, and publishes that view through the
  block's head votes and support bits.
- Build on the full payload of `head.root` when
  `should_build_on_full(store, head, slot)` holds, and on the empty node
  otherwise.
- Execution payload bid selection and inclusion-list handling are inherited from
  [Heze](../../heze/validator.md), with
  [`should_extend_payload`](./fork-choice.md#modified-should_extend_payload) as
  modified in the fork choice.

#### Constructing the `BeaconBlockBody`

*Note*: In this section, `state` is the parent state processed through any empty
slots up to the proposal slot using `process_slots`, before applying the block.

##### Head votes

Set `block.body.head_votes` to aggregates from the AC proposal view, up to
`MAX_HEAD_VOTES`. Each aggregate must satisfy the verification conditions in
[`process_head_vote`](./beacon-chain.md#new-process_head_vote). Votes of
`block.slot - 1` come first. The remaining space may hold votes of earlier slots
in the previous and current epochs that add seats for the block of their slot,
since these weigh builder payments.

Set `block.body.head_vote_support` to one `HeadVoteSupportBits` per included
aggregate, in the same order, with one bit per voter in that aggregate, in the
order of its `voter_indices`. Set a voter's bit if the proposer counted that
voter's vote as support in its previous slot head-vote view. A counted vote must
be of slot `block.slot - 1`, for a block in the accepted tree at proposal time
whose slot is no later than the vote's slot. Otherwise, clear the bit.

*Note*: A vote for an unknown block may be included with its support bits
cleared.

*TODO*: Specify aggregate selection when the proposal view exceeds
`MAX_HEAD_VOTES`, preserving the requirements of view merge.

##### Safe votes

Set `block.body.safe_votes` to aggregates from the safe vote pool, up to
`MAX_SAFE_VOTES`. Each aggregate must satisfy the verification conditions in
[`process_safe_vote`](./beacon-chain.md#new-process_safe_vote). A proposer
should prefer aggregates that add voters within the expiry window, and should
include a validator's second distinct vote of a round when it holds one, since
the fork choice reads equivocations.

##### Attestations

Set `block.body.attestations` to aggregates selected from the FG attestation
pool, up to `MAX_ATTESTATIONS_ELECTRA`. Each aggregate must satisfy the
verification conditions in
[`process_attestation`](./beacon-chain.md#modified-process_attestation),
including its epoch, committee encoding and signature.

A proposer should prefer aggregates that add target, progress or
pending-finality participation. An attestation for a previous height can still
contribute to a retained finality pair.

##### Attester slashings

Set `block.body.attester_slashings` to valid EIP-8453 attester slashing evidence
and `block.body.legacy_attester_slashings` to valid pre-EIP-8453 evidence. Each
list may contain up to `MAX_ATTESTER_SLASHINGS_ELECTRA` items.

The evidence must satisfy `process_attester_slashing` or
`process_legacy_attester_slashing`, respectively, against the state at its
position in block processing.

### Head voting

A validator on the head vote committee of `slot` creates, signs and broadcasts a
`HeadVoteMessage` for that slot.

*Note*: Head voting occurs one quarter of the way through the slot, after
reconciling with the previous slot's votes as published by the slot's proposals
(view merge). A validator that has just started or finished syncing must observe
one complete slot before voting: it cannot reconcile against votes it was not
online to receive.

The head-vote deadline is `get_head_vote_due_ms()` into the slot. At the
deadline, the validator obtains its head from
[`get_voter_head`](./fork-choice.md#new-get_voter_head), which applies view
merge, the stabilization anchor and the FG restrictions over the frozen voting
view.

#### Head vote data

First, the validator constructs `head_vote_data`, a
[`HeadVoteData`](./beacon-chain.md#new-headvotedata) object:

- Let `head` be the head selected by the AC voting procedure for `slot`.
- Set `head_vote_data.slot = slot`.
- Set `head_vote_data.beacon_block_root = hash_tree_root(head)`.
- Set `head_vote_data.payload_status` to `PAYLOAD_STATUS_PENDING` if
  `head.slot == slot`. Otherwise, set it to the payload status of `head`
  selected by the AC voting procedure, `PAYLOAD_STATUS_FULL` or
  `PAYLOAD_STATUS_EMPTY`.

The AC voting procedure applies view merge, AC locks and FG restrictions using
its voting view.

#### Construct head vote

The validator creates `head_vote_message` as a
[`HeadVoteMessage`](./beacon-chain.md#new-headvotemessage):

- Set `head_vote_message.validator_index = validator_index`.
- Set `head_vote_message.data = head_vote_data`.
- Set `head_vote_message.signature` to
  `get_head_vote_signature(state, head_vote_data, privkey)`.

```python
def get_head_vote_signature(state: BeaconState, data: HeadVoteData, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_HEAD_VOTE, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    return bls.Sign(privkey, signing_root)
```

The validator must record the selected root before signing and must not sign
another head for the same slot.

#### Broadcast head vote

The validator broadcasts `head_vote_message` on the global `head_vote`
[topic](./p2p-interface.md#new-head_vote) and processes it locally.

### Safe voting

Every active validator creates, signs and broadcasts one `SafeVoteMessage` per
round, in its assigned sub-round.

#### Safe vote assignment

Safe votes are cast across the first `SLOTS_PER_ROUND - 2` slots of the round,
after the round's grades complete and early enough that every vote arrives
before the next round's earliest grade cutoff. The assignment is a pure function
of the validator index: it schedules bandwidth and carries no other meaning.

```python
def compute_safe_vote_sub_round(validator_index: ValidatorIndex) -> Uint64:
    return Uint64(validator_index) % (Uint64(SLOTS_PER_ROUND) - 2)
```

A validator casts its safe vote for `round` one quarter of the way through slot
`compute_start_slot_at_round(round) + compute_safe_vote_sub_round(validator_index)`.

*Note*: When the validator's attestation committee slot falls in the same
sub-round, the safe vote and the FG attestation may share a transport envelope;
bundling is a networking optimization with no consensus meaning.

#### Safe vote data

First, the validator constructs `safe_vote_data`, a
[`SafeVoteData`](./beacon-chain.md#new-safevotedata) object:

- Let `node` be the node returned by the fork choice's safe-vote selection,
  [`get_safe_vote_node`](./fork-choice.md#new-get_safe_vote_node), which applies
  the grade-0 veto between the anchor and the confirmed node.
- Set `safe_vote_data.round` to the current round.
- Set `safe_vote_data.beacon_block_root = node.root`.
- Set `safe_vote_data.payload_status = node.payload_status`.

#### Construct safe vote

The validator creates `safe_vote_message` as a
[`SafeVoteMessage`](./beacon-chain.md#new-safevotemessage):

- Set `safe_vote_message.validator_index = validator_index`.
- Set `safe_vote_message.data = safe_vote_data`.
- Set `safe_vote_message.signature` to
  `get_safe_vote_signature(state, safe_vote_data, privkey)`.

```python
def get_safe_vote_signature(state: BeaconState, data: SafeVoteData, privkey: int) -> BLSSignature:
    epoch = compute_epoch_at_slot(compute_start_slot_at_round(data.round))
    domain = get_domain(state, DOMAIN_SAFE_VOTE, epoch)
    signing_root = compute_signing_root(data, domain)
    return bls.Sign(privkey, signing_root)
```

The validator must record the selected node before signing and must not sign
another safe vote for the same round.

#### Broadcast safe vote

The validator broadcasts `safe_vote_message` on the global `safe_vote`
[topic](./p2p-interface.md#new-safe_vote) and processes it locally.

### Attesting

A validator attempts to create an FG attestation in the slot of its attestation
committee using the rules below. It sends no new attestation if there is no FG
source or if its signing history suppresses the vote.

*Note*: A height pair is emitted only in rounds where
[`has_fresh_safe_quorum`](./fork-choice.md#new-has_fresh_safe_quorum) holds —
the stabilization layer's fresh quorum evidence. Without it, the attestation
carries its finality pair alone.

The FG attestation deadline is `get_attestation_due_ms()` into the committee's
assigned slot. At the deadline, the validator takes a single observation of the
fork choice — the source below through
[`get_fg_target_source`](./fork-choice.md#new-get_fg_target_source) and the head
through [`get_fg_finality_source`](./fork-choice.md#new-get_fg_finality_source)
— so the pair rules read one consistent view.

#### Attestation data

First, obtain `source` and `head` from the same AC-to-FG observation. The source
is the deepest block in the viable tree passing the fast test in the applicable
confirmation update. If no such block exists, the validator does not attest.

Let `source_state` and `head_state` be the states after processing `source` and
`head`, respectively:

- Let `target` be a copy of `source_state.target_checkpoint`.
- Let `justified = head_state.justified_checkpoint`.
- Let `finalized_height = head_state.finalized_checkpoint.height`.

If `target.root == Root()` because `source` advanced the height, set
`target.root = hash_tree_root(source)`.

*Note*: The height vote comes from the source state. The finality pair comes
from the head state.

##### Finality pair

The validator selects the finality pair using `get_finality_vote`:

```python
def get_finality_vote(
    record: FinalitySigningRecord,
    justified: HeightCheckpoint,
    finalized_height: Height,
) -> HeightCheckpoint:
    height, root = justified.height, justified.root
    if height <= finalized_height:
        return HeightCheckpoint.empty()
    if record.targets.get(height) not in (None, root):
        return HeightCheckpoint.empty()
    if height in record.timeouts:
        return HeightCheckpoint.empty()
    if record.finality_locks.get(height) not in (None, root):
        return HeightCheckpoint.empty()
    return justified.copy()
```

##### Height pair

The validator selects the height pair using `get_height_vote`:

```python
def get_height_vote(
    record: FinalitySigningRecord,
    target: HeightCheckpoint,
    finality: HeightCheckpoint,
) -> tuple[HeightCheckpoint, bool] | None:
    height, root = target.height, target.root
    if height == 0 or root == Root():
        return None

    lock = record.finality_locks.get(height)
    if finality != HeightCheckpoint.empty() and finality.height == height:
        lock = finality.root

    if height in record.timeouts:
        return target.copy(), True
    if lock is not None:
        if lock == root:
            return target.copy(), False
        return None
    if record.targets.get(height) in (None, root):
        return target.copy(), False
    return target.copy(), True
```

*Note*: The candidate finality pair constrains the height vote before it is
removed, if necessary, by `get_finality_attestation_data` below.

##### Construct data

Set `attestation_data` to
`get_finality_attestation_data(record, target, justified, finalized_height)`. If
it returns `None`, the validator sends no new attestation.

*Note*: The duplicate-vote checks suppress the entire attestation, including any
new finality pair.

```python
def get_finality_attestation_data(
    record: FinalitySigningRecord,
    target: HeightCheckpoint,
    justified: HeightCheckpoint,
    finalized_height: Height,
) -> AttestationData | None:
    finality = get_finality_vote(record, justified, finalized_height)
    vote = get_height_vote(record, target, finality)
    if vote is None:
        return None
    target, timeout = vote

    entries = record.entries.get(target.height, set())
    if (not timeout and len(entries) > 0) or target.root in entries:
        return None

    if finality != HeightCheckpoint.empty() and target.height <= finality.height:
        finality = HeightCheckpoint.empty()

    return AttestationData(target=target, timeout=Boolean(timeout), finality=finality)
```

##### Record attestation

Before signing, the validator records the selected `attestation_data`:

```python
def record_finality_attestation(record: FinalitySigningRecord, data: AttestationData) -> None:
    height, root = data.target.height, data.target.root
    record.entries.setdefault(height, set()).add(root)
    if data.finality != HeightCheckpoint.empty():
        record.finality_locks[data.finality.height] = data.finality.root
    if data.timeout:
        record.timeouts.add(height)
    else:
        record.targets.setdefault(height, root)
```

Selecting and recording the data must be serialized per validator key. The
record and selected data must be persisted before signing. See
[Protection best practices](#protection-best-practices) for interrupted duties.

#### Construct attestation

The validator creates `attestation` as a
[`SingleAttestation`](./beacon-chain.md#modified-singleattestation) with the
following fields:

- Set `attestation.committee_index` to the assigned committee index.
- Set `attestation.attester_index = validator_index`.
- Set `attestation.data = attestation_data`.
- Set `attestation.epoch` to the epoch of the assigned slot.
- Set `attestation.signature` to
  `get_attestation_signature(state, attestation_data, attestation.epoch, privkey)`.

```python
def get_attestation_signature(
    state: BeaconState,
    attestation_data: AttestationData,
    # [New in EIP8453]
    epoch: Epoch,
    privkey: int,
) -> BLSSignature:
    # [Modified in EIP8453]
    domain = get_domain(state, DOMAIN_FINALITY_ATTESTER, epoch)
    signing_root = compute_signing_root(attestation_data, domain)
    return bls.Sign(privkey, signing_root)
```

The signature covers `attestation.data`, but not `attestation.epoch` or
`attestation.committee_index`.

#### Broadcast attestation

The validator broadcasts `attestation` on the `attestation_{subnet_id}`
[topic](./p2p-interface.md#new-attestation_subnet_id) and processes it locally,
where `subnet_id = compute_subnet_for_attestation(attestation.committee_index)`.

```python
def compute_subnet_for_attestation(
    # [Modified in EIP8453]
    # Removed `committees_per_slot`
    # [Modified in EIP8453]
    # Removed `slot`
    committee_index: CommitteeIndex,
) -> SubnetID:
    """
    Return the subnet of the attestation committee at ``committee_index``.
    """
    # [Modified in EIP8453]
    return SubnetID(committee_index % ATTESTATION_SUBNET_COUNT)
```

### Attestation aggregation

Validators aggregate head votes and FG attestations separately. The messages
passed to the helpers below must have valid signatures under the same domain and
valid committee assignments for `state`.

*Note*: The helpers aggregate individual messages. Aggregates with overlapping
signers cannot be combined by adding their signatures.

#### Aggregation selection

Aggregators self-select with a selection proof, as in prior upgrades: a
validator is an aggregator when the hash of its proof clears a modulo chosen to
yield `TARGET_AGGREGATORS_PER_COMMITTEE` expected aggregators per group. The
groups are the slot's head vote committee, the sub-round's safe voters, and the
round's attestation committee, each with its own proof domain so one signature
never serves two roles.

```python
def is_selected_aggregator(selection_proof: BLSSignature, members: Uint64) -> bool:
    modulo = max(1, members // TARGET_AGGREGATORS_PER_COMMITTEE)
    return bytes_to_uint64(sha256(selection_proof)[0:8]) % modulo == 0
```

##### Head vote aggregation selection

A member of the slot's head vote committee is an aggregator for the slot when
`is_selected_aggregator(proof, HEAD_VOTE_COMMITTEE_SIZE)` holds for its proof. A
validator holding several seats gets no additional selection chances.

```python
def get_head_vote_aggregator_proof(state: BeaconState, slot: Slot, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_HEAD_VOTE_AGGREGATOR, compute_epoch_at_slot(slot))
    signing_root = compute_signing_root(slot, domain)
    return bls.Sign(privkey, signing_root)
```

##### Safe vote aggregation selection

An active validator is a safe vote aggregator for the round when
`is_selected_aggregator(proof, members)` holds for its proof, where `members` is
the number of active validators assigned to its sub-round,
`len(get_active_validator_indices(state, epoch)) // (SLOTS_PER_ROUND - 2)`.

```python
def get_safe_vote_aggregator_proof(state: BeaconState, round: Round, privkey: int) -> BLSSignature:
    epoch = compute_epoch_at_slot(compute_start_slot_at_round(round))
    domain = get_domain(state, DOMAIN_SAFE_VOTE_AGGREGATOR, epoch)
    signing_root = compute_signing_root(round, domain)
    return bls.Sign(privkey, signing_root)
```

##### FG attestation aggregation selection

A member of an attestation committee is an aggregator for the round when
`is_selected_aggregator(proof, members)` holds for its proof, where `members` is
its committee's size. A validator sits on one committee per round, so the proof
signs the round alone.

```python
def get_attestation_aggregator_proof(
    state: BeaconState, round: Round, privkey: int
) -> BLSSignature:
    epoch = compute_epoch_at_slot(compute_start_slot_at_round(round))
    domain = get_domain(state, DOMAIN_ATTESTATION_AGGREGATOR, epoch)
    signing_root = compute_signing_root(round, domain)
    return bls.Sign(privkey, signing_root)
```

#### Construct aggregate

##### Head votes

Construct `aggregate_vote` using `get_aggregate_head_vote` with head vote
messages for the same slot and block root. A validator holding several seats in
the committee is listed and signs once, and its vote counts for each of its
seats.

```python
def get_aggregate_head_vote(state: BeaconState, messages: Sequence[HeadVoteMessage]) -> HeadVote:
    """
    Aggregate head vote messages with identical data and distinct signers.
    """
    assert len(messages) > 0
    data = messages[0].data
    assert all(message.data == data for message in messages)
    signatures = {message.validator_index: message.signature for message in messages}
    assert len(signatures) == len(messages)

    for validator_index in signatures:
        assert validator_index in get_head_vote_committee(state, data.slot)

    voter_indices = sorted(signatures)
    return HeadVote(
        voter_indices=HeadVoteCommitteeIndices(data=voter_indices),
        data=data,
        signature=bls.Aggregate([signatures[index] for index in voter_indices]),
    )
```

##### Safe vote aggregation

Construct `aggregate_safe_vote` using `get_aggregate_safe_vote` with safe vote
messages for the same round and node. Safe votes aggregate by value, regardless
of attestation committees: in good times, the round's votes collapse into a few
aggregates.

```python
def get_aggregate_safe_vote(messages: Sequence[SafeVoteMessage]) -> SafeVote:
    """
    Return the aggregate safe vote for the ``messages`` of one round and node.
    """
    assert len(messages) > 0
    data = messages[0].data
    assert all(message.data == data for message in messages)
    signatures = {message.validator_index: message.signature for message in messages}
    assert len(signatures) == len(messages)

    voter_indices = sorted(signatures)
    return SafeVote(
        voter_indices=SafeVoteIndices(data=voter_indices),
        data=data,
        signature=bls.Aggregate([signatures[index] for index in voter_indices]),
    )
```

##### FG attestations

Construct `aggregate_attestation` using `get_aggregate_attestation` with
individual attestations for the same data and epoch. Attestations cast in
different rounds of the same epoch can be aggregated together.

```python
def get_aggregate_attestation(
    state: BeaconState, attestations: Sequence[SingleAttestation]
) -> Attestation:
    """
    Aggregate attestations with identical data and epoch, and distinct signers.
    """
    assert len(attestations) > 0
    data = attestations[0].data
    epoch = attestations[0].epoch
    assert all(a.data == data and a.epoch == epoch for a in attestations)
    participants = {a.attester_index for a in attestations}
    assert len(participants) == len(attestations)

    committee_bits = AttestationCommitteeBits()
    for attestation in attestations:
        assert attestation.committee_index < ATTESTATION_COMMITTEES_PER_ROUND
        committee_bits[attestation.committee_index] = Boolean(True)

    aggregation_bits = get_attestation_aggregation_bits(state, epoch, committee_bits, participants)
    return Attestation(
        aggregation_bits=aggregation_bits,
        data=data,
        signature=bls.Aggregate([a.signature for a in attestations]),
        committee_bits=committee_bits,
        epoch=epoch,
    )
```

##### Aggregation bits

`get_attestation_aggregation_bits` encodes signers in committee-index order,
matching `get_aggregate_participants` in the beacon-chain specification. The
size bound applies to all members of the represented committees, not only the
signers. Split messages into separate aggregates when the bound would be
exceeded.

```python
def get_attestation_aggregation_bits(
    state: BeaconState,
    epoch: Epoch,
    committee_bits: AttestationCommitteeBits,
    participants: set[ValidatorIndex],
) -> AggregationBits:
    """
    Encode participants in the concatenation of the selected attestation
    committees.
    """
    aggregation_bits = AggregationBits()
    represented_participants: set[ValidatorIndex] = set()
    for committee_index in get_committee_indices(committee_bits):
        committee = get_attestation_committee(state, epoch, committee_index)
        assert len(aggregation_bits) + len(committee) <= MAX_VALIDATORS_PER_AGGREGATE
        for validator_index in committee:
            is_participant = validator_index in participants
            aggregation_bits.append(Boolean(is_participant))
            if is_participant:
                represented_participants.add(validator_index)
    assert represented_participants == participants
    return aggregation_bits
```

#### Aggregate wrappers

Aggregates travel on gossip wrapped with the aggregator's identity and selection
proof, and the wrapper is signed under `DOMAIN_AGGREGATE_AND_PROOF`. FG
attestation aggregates reuse the inherited `AggregateAndProof` and
`SignedAggregateAndProof` containers; head votes and safe votes get their own.

##### New `HeadVoteAggregateAndProof`

```python
class HeadVoteAggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: HeadVote
    selection_proof: BLSSignature
```

##### New `SignedHeadVoteAggregateAndProof`

```python
class SignedHeadVoteAggregateAndProof(Container):
    message: HeadVoteAggregateAndProof
    signature: BLSSignature
```

##### New `SafeVoteAggregateAndProof`

```python
class SafeVoteAggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: SafeVote
    selection_proof: BLSSignature
```

##### New `SignedSafeVoteAggregateAndProof`

```python
class SignedSafeVoteAggregateAndProof(Container):
    message: SafeVoteAggregateAndProof
    signature: BLSSignature
```

#### Broadcast aggregate

An aggregator broadcasts its wrapped aggregates on the matching topic and
retains them for block inclusion:

- Head vote aggregates by two quarters of the way through the vote's slot, on
  `head_vote_aggregate`, so the next slot's proposer holds them in time for view
  merge.
- Safe vote aggregates by two quarters of the way through the aggregator's
  sub-round slot, on `safe_vote_aggregate`, covering every vote of the round
  seen so far, one aggregate per distinct `SafeVoteData`.
- FG attestation aggregates at the inherited aggregate deadline of the
  committee's slot, on `attestation_aggregate`.

*Note*: Gossip deduplication must use the data and signers, since an FG
aggregate's epoch is not signed.

*Note*: An FG aggregate's epoch must be between
`compute_epoch_at_slot(state.finalized_slot)` and `get_current_epoch(state)`,
inclusive, when included in a block. Its data must also remain valid against the
inclusion state.
