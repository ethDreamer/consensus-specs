# Trident -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Participation flag indices](#participation-flag-indices)
  - [Participation flag weights](#participation-flag-weights)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Time parameters](#time-parameters)
  - [Committee parameters](#committee-parameters)
  - [Max operations per block](#max-operations-per-block)
- [Custom types](#custom-types)
  - [New `Height`](#new-height)
  - [New `Round`](#new-round)
  - [New `GoldfishCommitteeBits`](#new-goldfishcommitteebits)
  - [New `RoundSubnetBits`](#new-roundsubnetbits)
  - [New `HeightParticipation`](#new-heightparticipation)
  - [New `GoldfishCommittee`](#new-goldfishcommittee)
  - [New `GoldfishAggregates`](#new-goldfishaggregates)
  - [New `StabilizationAggregates`](#new-stabilizationaggregates)
  - [New `FinalityAggregates`](#new-finalityaggregates)
  - [New `TridentSlashings`](#new-tridentslashings)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`HeightCheckpoint`](#heightcheckpoint)
    - [`GoldfishVoteData`](#goldfishvotedata)
    - [`GoldfishVote`](#goldfishvote)
    - [`GoldfishAggregate`](#goldfishaggregate)
    - [`IncludedGoldfishVotes`](#includedgoldfishvotes)
    - [`StabilizationData`](#stabilizationdata)
    - [`HeightVote`](#heightvote)
    - [`FinalityVote`](#finalityvote)
    - [`FinalityData`](#finalitydata)
    - [`TridentAttestation`](#tridentattestation)
    - [`StabilizationAggregate`](#stabilizationaggregate)
    - [`FinalityAggregate`](#finalityaggregate)
    - [`FinalityVoteEvidence`](#finalityvoteevidence)
    - [`TridentSlashing`](#tridentslashing)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
- [Helpers](#helpers)
  - [Math](#math)
    - [New `compute_round_at_slot`](#new-compute_round_at_slot)
    - [New `compute_round_opening_slot`](#new-compute_round_opening_slot)
  - [Participation flags](#participation-flags)
    - [New `remove_flag`](#new-remove_flag)
  - [Predicates](#predicates)
    - [New `is_empty_height_vote`](#new-is_empty_height_vote)
    - [New `is_empty_finality_vote`](#new-is_empty_finality_vote)
    - [New `is_slashable_trident_evidence`](#new-is_slashable_trident_evidence)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_quorum_threshold`](#new-get_quorum_threshold)
    - [New `get_height_participant_indices`](#new-get_height_participant_indices)
    - [New `get_height_quorum_weight`](#new-get_height_quorum_weight)
    - [New `get_goldfish_committee`](#new-get_goldfish_committee)
    - [New `get_goldfish_committee_at`](#new-get_goldfish_committee_at)
    - [New `get_round_subnet_members`](#new-get_round_subnet_members)
    - [New `get_round_base_reward`](#new-get_round_base_reward)
    - [New `get_goldfish_seat_reward`](#new-get_goldfish_seat_reward)
  - [Beacon state mutators](#beacon-state-mutators)
    - [New `advance_height`](#new-advance_height)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `process_operations`](#modified-process_operations)
    - [New `process_goldfish_votes`](#new-process_goldfish_votes)
    - [New `process_stabilization_aggregate`](#new-process_stabilization_aggregate)
    - [New `process_finality_aggregate`](#new-process_finality_aggregate)
    - [New `process_finality_vote`](#new-process_finality_vote)
    - [New `process_trident_slashing`](#new-process_trident_slashing)
    - [New `process_height_events`](#new-process_height_events)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [New `process_goldfish_committee_update`](#new-process_goldfish_committee_update)
    - [New `is_waiting_on_timeout_delay`](#new-is_waiting_on_timeout_delay)
    - [New `get_leak_identified_indices`](#new-get_leak_identified_indices)
    - [Modified `process_inactivity_updates`](#modified-process_inactivity_updates)
    - [Modified `get_inactivity_penalty_deltas`](#modified-get_inactivity_penalty_deltas)
    - [Modified `process_rewards_and_penalties`](#modified-process_rewards_and_penalties)

<!-- mdformat-toc end -->

## Introduction

Trident replaces the Casper FFG finality gadget and the LMD-GHOST fork choice
with the decoupled consensus protocol: a Goldfish available chain, a
relative-majority stabilization gadget, and an accountable finality gadget,
exposing three nested chain tips (confirmed, stable, finalized). The protocol
and its machine-checked consensus proofs are specified in the
`verified-consensus` formalization; this document transcribes the state
transition layer (the chain state machine of its Section 4) onto the beacon
state.

Deliberate deviations from the verified model are marked with *Note* paragraphs.
The main ones are: attestations are split into two independently signed and
aggregated components (the model signs one combined attestation); committees are
stake-weighted samples (the model takes committees as premises); and the
validator set and weights follow the beacon chain's churn (the model fixes
them), with cross-set safety resting on weak subjectivity as today.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Constants

### Participation flag indices

Height participation flags record a validator's contribution at the current
height. They are reset when the height advances, not per epoch.

| Name                         | Value |
| ---------------------------- | ----- |
| `HEIGHT_TARGET_FLAG_INDEX`   | `0`   |
| `HEIGHT_PROGRESS_FLAG_INDEX` | `1`   |
| `HEIGHT_FINALIZE_FLAG_INDEX` | `2`   |

### Participation flag weights

The weights of the removed FFG duties (source, target, head) are reassigned to
the Trident duties so that total issuance is unchanged. Stabilization votes
carry no separate weight: an honest validator emits the stabilization and
finality components together, so the finality-component rewards pay for both.

| Name                     | Value        |
| ------------------------ | ------------ |
| `GOLDFISH_VOTE_WEIGHT`   | `Uint64(14)` |
| `HEIGHT_TARGET_WEIGHT`   | `Uint64(20)` |
| `HEIGHT_PROGRESS_WEIGHT` | `Uint64(8)`  |
| `FINALIZE_WEIGHT`        | `Uint64(12)` |

### Domain types

| Name                        | Value                      |
| --------------------------- | -------------------------- |
| `DOMAIN_GOLDFISH_VOTE`      | `DomainType("0x1A000000")` |
| `DOMAIN_STABILIZATION_VOTE` | `DomainType("0x1B000000")` |
| `DOMAIN_FINALITY_VOTE`      | `DomainType("0x1C000000")` |

## Preset

### Time parameters

The model constrains these parameters: `SLOTS_PER_ROUND >= 3`,
`SG_EXPIRY_WINDOW >= 1`, `4 <= SLOTS_PER_ROUND * SG_EXPIRY_WINDOW`,
`NON_JUSTIFIABLE_HEIGHT_PERIOD >= 5` (the paper permits `>= 4`, but the proved
finality claim requires `>= 5`), and `MAX_FINALITY_DEBT >= 2`. The timeout delay
is fixed at two rounds, the protocol's value. `SLOTS_PER_ROUND` is chosen well
above the minimum to leave aggregation slack at the grade cutoffs and to bound
per-validator signing frequency.

| Name                            | Value                |
| ------------------------------- | -------------------- |
| `SLOTS_PER_ROUND`               | `Uint64(2**3)` (= 8) |
| `SG_EXPIRY_WINDOW`              | `Uint64(2**3)` (= 8) |
| `NON_JUSTIFIABLE_HEIGHT_PERIOD` | `Uint64(2**3)` (= 8) |
| `MAX_FINALITY_DEBT`             | `Uint64(2**1)` (= 2) |

### Committee parameters

*Note*: Goldfish counts committee seats rather than stake, so seats are
allocated by balance-weighted sampling with replacement: one validator may
occupy several seats, following the payload timeliness committee's precedent.
The sampler walks a shuffled candidate sequence cyclically, accepting each visit
of a validator independently with probability
`effective_balance / MAX_EFFECTIVE_BALANCE_ELECTRA`, and stops at
`GOLDFISH_COMMITTEE_SIZE` seats. Every full cycle visits each active validator
exactly once, and acceptance is exactly proportional to effective balance per
visit, so any deviation of seat shares from stake shares comes from the single
stopped boundary cycle and is bounded by one visit per validator. Seat shares
are therefore *not exactly* stake-proportional: the boundary slightly favors
higher-balance validators. Simulation at mainnet parameters over adversarial
balance splits bounds the deviation at about 0.1% relative per balance class,
with seat-count concentration at least as good as independent stake-proportional
sampling; at the minimal preset's scale the deviation is on the order of a few
percent, which is acceptable for testing only. The security property consumed by
the protocol is that an honest majority of stake yields an honest majority of
committee *seats* with high probability. The verified model takes the honest
committee majority by count as a premise (`HonestCommittees`) and does not model
the election; re-binding the model's committee membership to seat granularity is
future verification work.

| Name                      | Value                      |
| ------------------------- | -------------------------- |
| `GOLDFISH_COMMITTEE_SIZE` | `Uint64(2**14)` (= 16,384) |
| `ROUND_SUBNET_COUNT`      | `Uint64(2**6)` (= 64)      |

### Max operations per block

| Name                           | Value                  |
| ------------------------------ | ---------------------- |
| `MAX_GOLDFISH_AGGREGATES`      | `Uint64(2**6)` (= 64)  |
| `MAX_STABILIZATION_AGGREGATES` | `Uint64(2**7)` (= 128) |
| `MAX_FINALITY_AGGREGATES`      | `Uint64(2**7)` (= 128) |
| `MAX_TRIDENT_SLASHINGS`        | `Uint64(2**4)` (= 16)  |

## Custom types

### New `Height`

```python
class Height(Uint64):
    """
    A finality-gadget height. Heights count justification and progress
    events and are separate from slots. Genesis is justified and
    finalized at height ``0``, and every chain starts at height ``1``.
    """
```

### New `Round`

```python
class Round(Uint64):
    """
    A stabilization-gadget round of ``SLOTS_PER_ROUND`` slots.
    """
```

### New `GoldfishCommitteeBits`

```python
class GoldfishCommitteeBits(ProgressiveBitList):
    """
    The participation bits of a Goldfish committee, in committee order.
    """
```

### New `RoundSubnetBits`

```python
class RoundSubnetBits(ProgressiveBitList):
    """
    The participation bits of a round subnet, in ascending order of the
    subnet's member validator indices.
    """
```

### New `HeightParticipation`

```python
class HeightParticipation(ProgressiveList[ParticipationFlags]):
    """
    The height participation flags of all validators at the current
    height.
    """
```

### New `GoldfishCommittee`

```python
class GoldfishCommittee(ProgressiveList[ValidatorIndex]):
    """
    A Goldfish committee: seat positions in order, with possible
    duplicate validator indices.
    """
```

### New `GoldfishAggregates`

```python
class GoldfishAggregates(ProgressiveList[IncludedGoldfishVotes]):
    """
    The Goldfish votes included in a beacon block, with their support
    bits.
    """
```

### New `StabilizationAggregates`

```python
class StabilizationAggregates(ProgressiveList[StabilizationAggregate]):
    """
    The stabilization-vote aggregates included in a beacon block.
    """
```

### New `FinalityAggregates`

```python
class FinalityAggregates(ProgressiveList[FinalityAggregate]):
    """
    The finality-vote aggregates included in a beacon block.
    """
```

### New `TridentSlashings`

```python
class TridentSlashings(ProgressiveList[TridentSlashing]):
    """
    The Trident slashings included in a beacon block.
    """
```

## Containers

### New containers

#### `HeightCheckpoint`

```python
class HeightCheckpoint(Container):
    height: Height
    root: Root
```

#### `GoldfishVoteData`

```python
class GoldfishVoteData(Container):
    slot: Slot
    beacon_block_root: Root
```

#### `GoldfishVote`

The unaggregated wire form of a Goldfish vote.

```python
class GoldfishVote(Container):
    validator_index: ValidatorIndex
    data: GoldfishVoteData
    signature: BLSSignature
```

#### `GoldfishAggregate`

```python
class GoldfishAggregate(Container):
    data: GoldfishVoteData
    aggregation_bits: GoldfishCommitteeBits
    signature: BLSSignature
```

#### `IncludedGoldfishVotes`

An honest proposer includes every previous-slot Goldfish vote it holds and marks
in `support_bits` exactly the votes whose head block it held at proposal time
(the resolved subset). The support bits record the proposer's view; they are not
a second set of votes.

```python
class IncludedGoldfishVotes(Container):
    aggregate: GoldfishAggregate
    support_bits: GoldfishCommitteeBits
```

#### `StabilizationData`

```python
class StabilizationData(Container):
    round: Round
    safe_root: Root
```

#### `HeightVote`

A height vote `(h, T, is_timeout)` names the block `T` that brought the chain
into height `h` on the validator's source. `is_timeout=False` is a target vote
and `is_timeout=True` is a timeout naming the entry it times out at. A `height`
of `0` encodes the empty height vote, which is valid: heights of votes are
always at least `1`.

```python
class HeightVote(Container):
    height: Height
    entry_root: Root
    is_timeout: Boolean
```

#### `FinalityVote`

A finality vote `(h_f, T_f)` finalizes the justified target `T_f` at height
`h_f`. A `height` of `0` encodes the empty finality vote.

```python
class FinalityVote(Container):
    height: Height
    target_root: Root
```

#### `FinalityData`

```python
class FinalityData(Container):
    round: Round
    height_vote: HeightVote
    finality_vote: FinalityVote
```

#### `TridentAttestation`

The unaggregated wire form of a combined attestation: one message, two
independently signed components. Every stabilization-gadget rule reads only the
stabilization component, and the finality gadget reads only the finality
component.

*Note*: The verified model signs the combined attestation as one object. The
split preserves every reader (no rule cross-checks the two components) and keeps
the anti-slashing record update atomic, since both components are produced and
recorded in one duty. See `create_attestation` in the validator document.

```python
class TridentAttestation(Container):
    validator_index: ValidatorIndex
    stabilization: StabilizationData
    finality: FinalityData
    stabilization_signature: BLSSignature
    finality_signature: BLSSignature
```

#### `StabilizationAggregate`

```python
class StabilizationAggregate(Container):
    subnet_id: Uint64
    data: StabilizationData
    aggregation_bits: RoundSubnetBits
    signature: BLSSignature
```

#### `FinalityAggregate`

```python
class FinalityAggregate(Container):
    subnet_id: Uint64
    data: FinalityData
    aggregation_bits: RoundSubnetBits
    signature: BLSSignature
```

#### `FinalityVoteEvidence`

```python
class FinalityVoteEvidence(Container):
    validator_index: ValidatorIndex
    data: FinalityData
    signature: BLSSignature
```

#### `TridentSlashing`

The two evidence items may be one and the same attestation: a finality vote can
conflict with the height vote of its own attestation.

```python
class TridentSlashing(Container):
    evidence_1: FinalityVoteEvidence
    evidence_2: FinalityVoteEvidence
```

### Modified containers

#### `BeaconBlockBody`

*Note*: The legacy `attestations` and `attester_slashings` fields are retained
for container compatibility but MUST be empty.

```python
# [Modified in Trident]
class BeaconBlockBody(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=17)

    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: ProposerSlashings
    attester_slashings: AttesterSlashings
    attestations: Attestations
    deposits: Deposits
    voluntary_exits: VoluntaryExits
    sync_aggregate: SyncAggregate
    bls_to_execution_changes: BLSToExecutionChanges
    signed_execution_payload_bid: SignedExecutionPayloadBid
    payload_attestations: PayloadAttestations
    parent_execution_requests: ExecutionRequests
    # [New in Trident]
    goldfish_votes: GoldfishAggregates
    # [New in Trident]
    stabilization_aggregates: StabilizationAggregates
    # [New in Trident]
    finality_aggregates: FinalityAggregates
    # [New in Trident]
    trident_slashings: TridentSlashings
```

#### `BeaconState`

*Note*: The legacy FFG fields (`justification_bits`,
`previous_justified_checkpoint`, `current_justified_checkpoint`,
`finalized_checkpoint`) are retained but frozen at their values from the fork
transition. The Trident finality state lives in the new fields. The chain state
machine's components map as follows: `h` is `height`, `T_h` is
`height_entry_root` (with `height_entry_slot` recording its slot for the timeout
delay), `nj` is `non_justifiable`, the three quorum bitmaps are
`height_participation`, `(J, h_j)` is `latest_justified`, and `(F, h_F)` is
`latest_finalized`.

```python
# [Modified in Trident]
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=54)

    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: BlockRoots
    state_roots: StateRoots
    historical_roots: HistoricalRoots
    eth1_data: Eth1Data
    eth1_data_votes: Eth1DataVotes
    eth1_deposit_index: Uint64
    validators: Validators
    balances: Balances
    randao_mixes: RandaoMixes
    slashings: Slashings
    previous_epoch_participation: EpochParticipation
    current_epoch_participation: EpochParticipation
    justification_bits: JustificationBits
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: InactivityScores
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    latest_block_hash: Hash32
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: HistoricalSummaries
    deposit_requests_start_index: Uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: PendingDeposits
    pending_partial_withdrawals: PendingPartialWithdrawals
    pending_consolidations: PendingConsolidations
    proposer_lookahead: ProposerLookahead
    builders: Builders
    next_withdrawal_builder_index: BuilderIndex
    execution_payload_availability: ExecutionPayloadAvailability
    builder_pending_payments: BuilderPendingPayments
    builder_pending_withdrawals: BuilderPendingWithdrawals
    latest_execution_payload_bid: ExecutionPayloadBid
    payload_expected_withdrawals: Withdrawals
    ptc_window: PayloadTimelinessCommitteeWindow
    # [New in Trident]
    previous_goldfish_committee: GoldfishCommittee
    # [New in Trident]
    height: Height
    # [New in Trident]
    height_entry_root: Root
    # [New in Trident]
    height_entry_slot: Slot
    # [New in Trident]
    non_justifiable: Boolean
    # [New in Trident]
    height_participation: HeightParticipation
    # [New in Trident]
    latest_justified: HeightCheckpoint
    # [New in Trident]
    latest_finalized: HeightCheckpoint
```

## Helpers

### Math

#### New `compute_round_at_slot`

```python
def compute_round_at_slot(slot: Slot) -> Round:
    return Round(slot // SLOTS_PER_ROUND)
```

#### New `compute_round_opening_slot`

```python
def compute_round_opening_slot(round: Round) -> Slot:
    return Slot(round * SLOTS_PER_ROUND)
```

### Participation flags

#### New `remove_flag`

```python
def remove_flag(flags: ParticipationFlags, flag_index: int) -> ParticipationFlags:
    """
    Return a new ``ParticipationFlags`` with ``flag_index`` cleared.
    """
    flag = ParticipationFlags(2**flag_index)
    return flags & ~flag
```

### Predicates

#### New `is_empty_height_vote`

```python
def is_empty_height_vote(vote: HeightVote) -> bool:
    return vote.height == 0
```

#### New `is_empty_finality_vote`

```python
def is_empty_finality_vote(vote: FinalityVote) -> bool:
    return vote.height == 0
```

#### New `is_slashable_trident_evidence`

A validator is slashable under either condition:

- **E1**: one finality vote is `(h, T)`, and one height vote at `h` is a
  timeout, or a target vote `(h, T', False)` with `T' != T`.
- **E2**: two target votes are `(h, T, False)` and `(h, T', False)` with
  `T != T'`.

A timeout is never an E2 occurrence, whatever entry it names. The two
occurrences may be in one attestation. Empty votes trigger neither condition.

```python
def is_slashable_trident_evidence(data_1: FinalityData, data_2: FinalityData) -> bool:
    # E1: data_1's finality vote against data_2's height vote
    if not is_empty_finality_vote(data_1.finality_vote) and not is_empty_height_vote(
        data_2.height_vote
    ):
        if data_1.finality_vote.height == data_2.height_vote.height:
            if data_2.height_vote.is_timeout:
                return True
            if data_2.height_vote.entry_root != data_1.finality_vote.target_root:
                return True
    # E1: data_2's finality vote against data_1's height vote
    if not is_empty_finality_vote(data_2.finality_vote) and not is_empty_height_vote(
        data_1.height_vote
    ):
        if data_2.finality_vote.height == data_1.height_vote.height:
            if data_1.height_vote.is_timeout:
                return True
            if data_1.height_vote.entry_root != data_2.finality_vote.target_root:
                return True
    # E2: two distinct target votes at one height
    if not is_empty_height_vote(data_1.height_vote) and not is_empty_height_vote(
        data_2.height_vote
    ):
        if (
            not data_1.height_vote.is_timeout
            and not data_2.height_vote.is_timeout
            and data_1.height_vote.height == data_2.height_vote.height
            and data_1.height_vote.entry_root != data_2.height_vote.entry_root
        ):
            return True
    return False
```

### Beacon state accessors

#### New `get_quorum_threshold`

```python
def get_quorum_threshold(state: BeaconState) -> Gwei:
    """
    Return ``q = ceil(2W / 3)`` where ``W`` is the total active balance.
    """
    total = get_total_active_balance(state)
    return Gwei((2 * total + 2) // 3)
```

#### New `get_height_participant_indices`

```python
def get_height_participant_indices(state: BeaconState, flag_index: int) -> set[ValidatorIndex]:
    output = set()
    for index in get_active_validator_indices(state, get_current_epoch(state)):
        if has_flag(state.height_participation[index], flag_index):
            output.add(index)
    return output
```

#### New `get_height_quorum_weight`

```python
def get_height_quorum_weight(state: BeaconState, flag_index: int) -> Gwei:
    participants = get_height_participant_indices(state, flag_index)
    return Gwei(sum(state.validators[index].effective_balance for index in participants))
```

#### New `get_goldfish_committee`

*Note*: The committee is a stake-weighted sample so that an honest stake
majority implies an honest committee majority by count, which Goldfish requires.
Acceptance sampling follows the proposer-selection pattern. A validator appears
at most once.

The committee depends on the seed and active set of the slot's epoch, which are
reconstructible from any later state, and on the effective balances in force
during that epoch, which are not: they are overwritten at the epoch transition.
`get_goldfish_committee` therefore requires a state whose current epoch is the
slot's epoch, and the one consumer that decodes across an epoch boundary — the
first block of an epoch carrying the previous slot's votes — reads the snapshot
taken by `process_goldfish_committee_update` instead, through
`get_goldfish_committee_at`.

```python
def get_goldfish_committee(state: BeaconState, slot: Slot) -> list[ValidatorIndex]:
    epoch = compute_epoch_at_slot(slot)
    assert epoch == get_current_epoch(state)
    seed = sha256(get_seed(state, epoch, DOMAIN_GOLDFISH_VOTE) + uint_to_bytes(slot))
    indices = get_active_validator_indices(state, epoch)
    return list(
        compute_balance_weighted_selection(
            state, indices, seed, size=GOLDFISH_COMMITTEE_SIZE, shuffle_indices=True
        )
    )
```

#### New `get_goldfish_committee_at`

```python
def get_goldfish_committee_at(state: BeaconState, slot: Slot) -> list[ValidatorIndex]:
    epoch = compute_epoch_at_slot(slot)
    if epoch == get_current_epoch(state):
        return get_goldfish_committee(state, slot)
    # Only the last slot of the previous epoch is ever decoded
    assert epoch + 1 == get_current_epoch(state)
    assert (slot + 1) % SLOTS_PER_EPOCH == 0
    return [ValidatorIndex(index) for index in state.previous_goldfish_committee]
```

#### New `get_round_subnet_members`

Subnet membership is anchored to the epoch of the round's opening slot, not the
epoch in which an aggregate happens to be processed: an aggregate built near the
end of the expiry window must decode to the same validators everywhere. The
anchored active set is reconstructible from any later state, since the registry
is append-only and activation and exit epochs describe past epochs faithfully.

```python
def get_round_subnet_members(
    state: BeaconState, round: Round, subnet_id: Uint64
) -> list[ValidatorIndex]:
    epoch = compute_epoch_at_slot(compute_round_opening_slot(round))
    members = []
    for index in get_active_validator_indices(state, epoch):
        if index % ROUND_SUBNET_COUNT == subnet_id:
            members.append(index)
    return members
```

#### New `get_round_base_reward`

The per-round share of the per-epoch base reward, so that per-duty rewards keep
total issuance at its pre-fork level.

```python
def get_round_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
    return Gwei(get_base_reward(state, index) * SLOTS_PER_ROUND // SLOTS_PER_EPOCH)
```

#### New `get_goldfish_seat_reward`

The reward for one included committee seat. Because seats are allocated
approximately in proportion to effective balance, a flat per-seat amount makes a
validator's expected Goldfish rewards linear in its stake: the
`GOLDFISH_VOTE_WEIGHT` share of total per-epoch base rewards, divided over the
epoch's seats. A per-seat reward proportional to the validator's own balance
would instead scale rewards with the square of the balance, since selection
probability already carries one factor.

```python
def get_goldfish_seat_reward(state: BeaconState) -> Gwei:
    total_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    total_base_rewards = Gwei(total_increments * get_base_reward_per_increment(state))
    goldfish_share = Gwei(total_base_rewards * GOLDFISH_VOTE_WEIGHT // WEIGHT_DENOMINATOR)
    return Gwei(goldfish_share // (GOLDFISH_COMMITTEE_SIZE * SLOTS_PER_EPOCH))
```

### Beacon state mutators

#### New `advance_height`

```python
def advance_height(state: BeaconState, block_root: Root) -> None:
    state.height = Height(state.height + 1)
    state.height_entry_root = block_root
    state.height_entry_slot = state.slot
    state.non_justifiable = Boolean(
        state.height % NON_JUSTIFIABLE_HEIGHT_PERIOD == 0
        and state.height - state.latest_finalized.height > MAX_FINALITY_DEBT
    )
    for index in range(len(state.height_participation)):
        flags = state.height_participation[index]
        flags = remove_flag(flags, HEIGHT_TARGET_FLAG_INDEX)
        flags = remove_flag(flags, HEIGHT_PROGRESS_FLAG_INDEX)
        state.height_participation[index] = flags
```

## Beacon chain state transition function

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    parent_slot = state.latest_block_header.slot

    process_parent_execution_payload(state, block)
    process_block_header(state, block)
    process_withdrawals(state)
    process_execution_payload_bid(state, block.body.signed_execution_payload_bid)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    # [Modified in Trident]
    process_operations(state, block.body, parent_slot)
    process_sync_aggregate(state, block.body.sync_aggregate)
    # [New in Trident]
    process_height_events(state, hash_tree_root(block))
```

#### Modified `process_operations`

*Note*: The legacy `attestations` and `attester_slashings` lists MUST be empty.
A block may not include finality or stabilization data from its own future:
every included aggregate's round is at most the round of the block's slot. There
is no lower bound; the state transition reads an included aggregate however old
it is.

```python
def process_operations(
    state: BeaconState,
    body: BeaconBlockBody,
    parent_slot: Slot,
) -> None:
    assert len(body.deposits) == 0
    # [New in Trident]
    assert len(body.attestations) == 0
    # [New in Trident]
    assert len(body.attester_slashings) == 0

    def for_ops(operations: Sequence[Any], fn: Callable[..., None], *args: Any) -> None:
        for operation in operations:
            fn(state, operation, *args)

    assert len(body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS
    assert len(body.voluntary_exits) <= MAX_VOLUNTARY_EXITS
    assert len(body.bls_to_execution_changes) <= MAX_BLS_TO_EXECUTION_CHANGES
    assert len(body.payload_attestations) <= MAX_PAYLOAD_ATTESTATIONS
    # [New in Trident]
    assert len(body.goldfish_votes) <= MAX_GOLDFISH_AGGREGATES
    # [New in Trident]
    assert len(body.stabilization_aggregates) <= MAX_STABILIZATION_AGGREGATES
    # [New in Trident]
    assert len(body.finality_aggregates) <= MAX_FINALITY_AGGREGATES
    # [New in Trident]
    assert len(body.trident_slashings) <= MAX_TRIDENT_SLASHINGS

    for_ops(body.proposer_slashings, process_proposer_slashing)
    # [New in Trident]
    for_ops(body.trident_slashings, process_trident_slashing)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    for_ops(body.payload_attestations, process_payload_attestation)
    # [New in Trident]
    for_ops(body.goldfish_votes, process_goldfish_votes)
    # [New in Trident]
    for_ops(body.stabilization_aggregates, process_stabilization_aggregate)
    # [New in Trident]
    for_ops(body.finality_aggregates, process_finality_aggregate)
```

#### New `process_goldfish_votes`

Included Goldfish votes have no effect on the finality state; they are processed
for inclusion rewards and validated so that the fork choice can read them from
blocks.

A validator occupying several seats appears at several committee positions; a
set bit at each position contributes the validator's pubkey once more to the
aggregate verification and earns one more seat reward. A validator broadcasts a
single signature; the aggregator includes that signature once per set seat bit,
so the aggregate verifies against the repeated pubkeys, as the payload
timeliness committee's indexed attestations do.

```python
def process_goldfish_votes(state: BeaconState, included: IncludedGoldfishVotes) -> None:
    aggregate = included.aggregate
    data = aggregate.data
    assert data.slot + 1 == state.slot
    committee = get_goldfish_committee_at(state, data.slot)
    assert len(aggregate.aggregation_bits) == len(committee)
    assert len(included.support_bits) == len(committee)
    participants = [
        committee[i] for i in range(len(committee)) if aggregate.aggregation_bits[i]
    ]
    assert len(participants) > 0
    # Support bits mark a subset of the participants
    for i in range(len(committee)):
        if included.support_bits[i]:
            assert aggregate.aggregation_bits[i]
    # Verify the aggregate signature, with repeated pubkeys for repeated seats
    pubkeys = [state.validators[index].pubkey for index in participants]
    domain = get_domain(state, DOMAIN_GOLDFISH_VOTE, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    assert bls.FastAggregateVerify(pubkeys, signing_root, aggregate.signature)
    # Reward each included seat and the proposer
    seat_reward = get_goldfish_seat_reward(state)
    proposer_reward_numerator = 0
    for index in participants:
        increase_balance(state, index, seat_reward)
        proposer_reward_numerator += seat_reward * PROPOSER_WEIGHT
    proposer_reward = Gwei(proposer_reward_numerator // (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT))
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```

#### New `process_stabilization_aggregate`

Stabilization votes have no effect on the finality state: every
stabilization-gadget rule reads them from the fork-choice store. Inclusion
validates them so that recovering nodes can refill their pools from blocks.

```python
def process_stabilization_aggregate(
    state: BeaconState, aggregate: StabilizationAggregate
) -> None:
    data = aggregate.data
    assert data.round <= compute_round_at_slot(state.slot)
    assert aggregate.subnet_id < ROUND_SUBNET_COUNT
    members = get_round_subnet_members(state, aggregate.data.round, aggregate.subnet_id)
    assert len(aggregate.aggregation_bits) == len(members)
    participants = [members[i] for i in range(len(members)) if aggregate.aggregation_bits[i]]
    assert len(participants) > 0
    pubkeys = [state.validators[index].pubkey for index in participants]
    epoch = compute_epoch_at_slot(compute_round_opening_slot(data.round))
    domain = get_domain(state, DOMAIN_STABILIZATION_VOTE, epoch)
    signing_root = compute_signing_root(data, domain)
    assert bls.FastAggregateVerify(pubkeys, signing_root, aggregate.signature)
```

#### New `process_finality_aggregate`

The finality component drives the chain state machine. A height vote counts only
when it names the chain's own entry at the current height: a target vote then
records target participation and progress, a timeout records progress alone, and
a vote naming another entry records nothing, while its finality vote is folded
regardless.

```python
def process_finality_aggregate(state: BeaconState, aggregate: FinalityAggregate) -> None:
    data = aggregate.data
    assert data.round <= compute_round_at_slot(state.slot)
    assert aggregate.subnet_id < ROUND_SUBNET_COUNT
    members = get_round_subnet_members(state, aggregate.data.round, aggregate.subnet_id)
    assert len(aggregate.aggregation_bits) == len(members)
    participants = [members[i] for i in range(len(members)) if aggregate.aggregation_bits[i]]
    assert len(participants) > 0
    pubkeys = [state.validators[index].pubkey for index in participants]
    epoch = compute_epoch_at_slot(compute_round_opening_slot(data.round))
    domain = get_domain(state, DOMAIN_FINALITY_VOTE, epoch)
    signing_root = compute_signing_root(data, domain)
    assert bls.FastAggregateVerify(pubkeys, signing_root, aggregate.signature)

    proposer_reward_numerator = 0
    for index in participants:
        proposer_reward_numerator += process_finality_vote(state, data, index)
    proposer_reward = Gwei(proposer_reward_numerator // (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT))
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```

#### New `process_finality_vote`

```python
def process_finality_vote(state: BeaconState, data: FinalityData, index: ValidatorIndex) -> Gwei:
    reward_numerator = Gwei(0)
    flags = state.height_participation[index]
    # Fold the finality vote
    if not is_empty_finality_vote(data.finality_vote):
        if (
            state.latest_justified.height > state.latest_finalized.height
            and data.finality_vote.height == state.latest_justified.height
            and data.finality_vote.target_root == state.latest_justified.root
            and not has_flag(flags, HEIGHT_FINALIZE_FLAG_INDEX)
        ):
            flags = add_flag(flags, HEIGHT_FINALIZE_FLAG_INDEX)
            reward = Gwei(get_round_base_reward(state, index) * FINALIZE_WEIGHT // WEIGHT_DENOMINATOR)
            increase_balance(state, index, reward)
            reward_numerator += reward * PROPOSER_WEIGHT
    # Fold the height vote, only when it names the chain's own entry
    if not is_empty_height_vote(data.height_vote):
        if (
            data.height_vote.height == state.height
            and data.height_vote.entry_root == state.height_entry_root
        ):
            if not has_flag(flags, HEIGHT_PROGRESS_FLAG_INDEX):
                flags = add_flag(flags, HEIGHT_PROGRESS_FLAG_INDEX)
                reward = Gwei(
                    get_round_base_reward(state, index) * HEIGHT_PROGRESS_WEIGHT // WEIGHT_DENOMINATOR
                )
                increase_balance(state, index, reward)
                reward_numerator += reward * PROPOSER_WEIGHT
            if not data.height_vote.is_timeout and not has_flag(flags, HEIGHT_TARGET_FLAG_INDEX):
                flags = add_flag(flags, HEIGHT_TARGET_FLAG_INDEX)
                reward = Gwei(
                    get_round_base_reward(state, index) * HEIGHT_TARGET_WEIGHT // WEIGHT_DENOMINATOR
                )
                increase_balance(state, index, reward)
                reward_numerator += reward * PROPOSER_WEIGHT
    state.height_participation[index] = flags
    return reward_numerator
```

#### New `process_trident_slashing`

```python
def process_trident_slashing(state: BeaconState, slashing: TridentSlashing) -> None:
    evidence_1 = slashing.evidence_1
    evidence_2 = slashing.evidence_2
    assert evidence_1.validator_index == evidence_2.validator_index
    assert is_slashable_trident_evidence(evidence_1.data, evidence_2.data)
    validator = state.validators[evidence_1.validator_index]
    assert is_slashable_validator(validator, get_current_epoch(state))
    for evidence in [evidence_1, evidence_2]:
        epoch = compute_epoch_at_slot(compute_round_opening_slot(evidence.data.round))
        domain = get_domain(state, DOMAIN_FINALITY_VOTE, epoch)
        signing_root = compute_signing_root(evidence.data, domain)
        assert bls.Verify(validator.pubkey, signing_root, evidence.signature)
    slash_validator(state, evidence_1.validator_index)
```

#### New `process_height_events`

Run once per block, after all operations are folded. A timeout-driven progress
quorum is consumed only by a block whose slot is at least the entry slot plus
two rounds: attestations are synchronous at the scale of rounds, so a timeout
may not be used to leave a height before the target votes cast at that height
have had time to arrive. An exact target quorum is consumed immediately.
Justification is disabled at every `NON_JUSTIFIABLE_HEIGHT_PERIOD`-th height
under finality debt, while target and timeout votes still advance the height, so
healing never waits on a justification that the debt rule forbids.

```python
def process_height_events(state: BeaconState, block_root: Root) -> None:
    quorum = get_quorum_threshold(state)
    # Finalize the pending justification on a finality quorum
    if (
        state.latest_justified.height > state.latest_finalized.height
        and get_height_quorum_weight(state, HEIGHT_FINALIZE_FLAG_INDEX) >= quorum
    ):
        state.latest_finalized = state.latest_justified.copy()
    # A target quorum justifies (unless non-justifiable) and advances
    if get_height_quorum_weight(state, HEIGHT_TARGET_FLAG_INDEX) >= quorum:
        if not state.non_justifiable:
            state.latest_justified = HeightCheckpoint(
                height=state.height, root=state.height_entry_root
            )
            for index in range(len(state.height_participation)):
                state.height_participation[index] = remove_flag(
                    state.height_participation[index], HEIGHT_FINALIZE_FLAG_INDEX
                )
        advance_height(state, block_root)
        return
    # A progress quorum advances only after the timeout delay
    if (
        get_height_quorum_weight(state, HEIGHT_PROGRESS_FLAG_INDEX) >= quorum
        and state.slot >= state.height_entry_slot + 2 * SLOTS_PER_ROUND
    ):
        advance_height(state, block_root)
```

### Epoch processing

#### Modified `process_epoch`

*Note*: `process_justification_and_finalization` is removed: justification and
finalization are per-block height events. `process_rewards_and_penalties` is
retained for inactivity penalties only; duty rewards are paid at inclusion.

```python
def process_epoch(state: BeaconState) -> None:
    # [Modified in Trident]
    # Removed `process_justification_and_finalization`
    # [Modified in Trident]
    process_inactivity_updates(state)
    # [Modified in Trident]
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_pending_deposits(state)
    process_pending_consolidations(state)
    process_builder_pending_payments(state)
    # [New in Trident]
    process_goldfish_committee_update(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_proposer_lookahead(state)
    process_ptc_window(state)
```

#### New `process_goldfish_committee_update`

The snapshot MUST be taken before `process_effective_balance_updates`: the
committee of the ending epoch's last slot is a function of the effective
balances in force during that epoch, and this is the last point at which they
are available. The snapshot serves the one decode that crosses the epoch
boundary, the first block of the next epoch carrying the last slot's votes. This
mirrors the payload timeliness committee's cached window, reduced to a single
committee because Goldfish votes expire after one slot.

```python
def process_goldfish_committee_update(state: BeaconState) -> None:
    committee = get_goldfish_committee(state, state.slot)
    snapshot = GoldfishCommittee()
    for index in committee:
        snapshot.append(index)
    state.previous_goldfish_committee = snapshot
```

#### New `is_waiting_on_timeout_delay`

A chain that holds a progress quorum without a target quorum inside the timeout
delay is waiting, not stalled: charging during it would leak honest validators
whose target votes are still in flight.

```python
def is_waiting_on_timeout_delay(state: BeaconState) -> bool:
    quorum = get_quorum_threshold(state)
    return (
        get_height_quorum_weight(state, HEIGHT_PROGRESS_FLAG_INDEX) >= quorum
        and get_height_quorum_weight(state, HEIGHT_TARGET_FLAG_INDEX) < quorum
        and state.slot < state.height_entry_slot + 2 * SLOTS_PER_ROUND
    )
```

#### New `get_leak_identified_indices`

The inactivity-leak ledger of the verified model (its proof-side `LeakLedger`),
read per epoch. Three layers identify validators outside the quorum bitmaps
while the corresponding counter is stalled; the identified set is their union,
so a validator is counted once however many layers identify it.

*Note*: **This section is an unverified economic adaptation.** The model's
ledger defines charges only; it attaches no penalties ("no charge changes
weights or transitions"), and its raw charge conditions fire on every
non-advancing block, healthy steady state included — so any deployable penalty
translation necessarily adds activation conditions the model does not have. The
adaptation here differs from the ledger as follows, each deviation charging
*less*, to *fewer* validators, than the raw ledger:

| Dimension   | Model ledger                                             | This adaptation                 |
| ----------- | -------------------------------------------------------- | ------------------------------- |
| Granularity | per block, scaled by the slot span                       | per epoch, unscaled             |
| Layers      | three separate charge counters, union for identification | union into one inactivity score |
| L1 trigger  | every block that does not advance the height             | height stalled for an epoch     |
| L2 trigger  | every block that does not advance the counter            | counter stalled for an epoch    |
| Waiting     | gates only the tightness statement                       | gates identification itself     |

Of the model's leak properties, exactly one is proved: L1 fairness — an honest
validator whose attestation is carried at its entry accrues no L1 charge. The
tightness target (whenever the chain is stalled, the identified weight is at
least `W - q`, so leaking it restores a quorum) is stated but not proved, and L2
fairness and fairness under censorship are open. Collapsing the layers into one
score lets the unproven L2 layers charge validators that the proven L1 fairness
protects; keeping three per-validator charge counters and translating them into
penalties separately is a flagged design option, deferred until the paper's
leak-identification section is available.

```python
def get_leak_identified_indices(state: BeaconState) -> set[ValidatorIndex]:
    identified: set[ValidatorIndex] = set()
    if is_waiting_on_timeout_delay(state):
        return identified
    active_indices = get_active_validator_indices(state, get_current_epoch(state))
    # L1: the height is stalled
    if state.slot >= state.height_entry_slot + SLOTS_PER_EPOCH:
        for index in active_indices:
            if not has_flag(state.height_participation[index], HEIGHT_PROGRESS_FLAG_INDEX):
                identified.add(index)
    # L2 target: justification is stalled at a justifiable height
    if (
        not state.non_justifiable
        and state.height > state.latest_justified.height
        and state.slot >= state.height_entry_slot + SLOTS_PER_EPOCH
    ):
        for index in active_indices:
            if not has_flag(state.height_participation[index], HEIGHT_TARGET_FLAG_INDEX):
                identified.add(index)
    # L2 finalize: finality is pending and stalled
    if (
        state.latest_finalized.height < state.latest_justified.height
        and state.slot >= state.height_entry_slot + SLOTS_PER_EPOCH
    ):
        for index in active_indices:
            if not has_flag(state.height_participation[index], HEIGHT_FINALIZE_FLAG_INDEX):
                identified.add(index)
    return identified
```

#### Modified `process_inactivity_updates`

```python
def process_inactivity_updates(state: BeaconState) -> None:
    # Skip the epoch prior to the activation of Trident
    if get_current_epoch(state) == TRIDENT_FORK_EPOCH:
        return
    # [Modified in Trident]
    identified = get_leak_identified_indices(state)
    for index in get_active_validator_indices(state, get_current_epoch(state)):
        if index in identified:
            state.inactivity_scores[index] += INACTIVITY_SCORE_BIAS
        else:
            state.inactivity_scores[index] -= min(
                INACTIVITY_SCORE_RECOVERY_RATE, state.inactivity_scores[index]
            )
```

#### Modified `get_inactivity_penalty_deltas`

*Note*: Penalties follow the inactivity score alone. Identification happens when
the score is incremented, so the previous-epoch target flags of the legacy
mechanism play no part.

```python
def get_inactivity_penalty_deltas(state: BeaconState) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    for index in get_active_validator_indices(state, get_current_epoch(state)):
        if state.inactivity_scores[index] > 0:
            penalty_numerator = (
                state.validators[index].effective_balance * state.inactivity_scores[index]
            )
            penalty_denominator = INACTIVITY_SCORE_BIAS * INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
            penalties[index] += Gwei(penalty_numerator // penalty_denominator)
    return rewards, penalties
```

#### Modified `process_rewards_and_penalties`

```python
def process_rewards_and_penalties(state: BeaconState) -> None:
    # No rewards or penalties in the epoch prior to the activation of Trident
    if get_current_epoch(state) == TRIDENT_FORK_EPOCH:
        return
    # [Modified in Trident]
    # Removed flag deltas; duty rewards are paid at inclusion
    rewards, penalties = get_inactivity_penalty_deltas(state)
    for index in range(len(state.validators)):
        increase_balance(state, ValidatorIndex(index), rewards[index])
        decrease_balance(state, ValidatorIndex(index), penalties[index])
```
