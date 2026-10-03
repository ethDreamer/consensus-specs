# Trident -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
- [Fork to Trident](#fork-to-trident)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the Trident upgrade. The latest finalized
block at the fork plays the role of the protocol's genesis block: it anchors the
new height machinery at height `1` with the FFG finalized checkpoint as the
justified and finalized entry of height `0`. This matches the verified model's
recovery-prefix construction, under which the consensus claims hold for a
non-genesis start.

Cross-fork accountable safety rests on weak subjectivity, as it does across
validator-set churn today: no claim relates finality certificates of the FFG era
to Trident certificates.

## Configs

Warning: this configuration is not definitive.

| Name                   | Value                                 |
| ---------------------- | ------------------------------------- |
| `TRIDENT_FORK_VERSION` | `Version("0x0a000000")`               |
| `TRIDENT_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Fork to Trident

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == TRIDENT_FORK_EPOCH`, an irregular state
change is made to upgrade to Trident.

The upgrade occurs after the completion of the inner loop of `process_slots`
that sets `state.slot` equal to `TRIDENT_FORK_EPOCH * SLOTS_PER_EPOCH`.

```python
def upgrade_to_trident(pre: heze.BeaconState) -> BeaconState:
    epoch = compute_epoch_at_slot(pre.slot)
    anchor_root = pre.finalized_checkpoint.root
    anchor_slot = compute_start_slot_at_epoch(pre.finalized_checkpoint.epoch)
    height_participation = HeightParticipation()
    for _ in range(len(pre.validators)):
        height_participation.append(ParticipationFlags(0b0000_0000))
    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [New in Trident]
            current_version=TRIDENT_FORK_VERSION,
            epoch=epoch,
        ),
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        eth1_data=pre.eth1_data,
        eth1_data_votes=pre.eth1_data_votes,
        eth1_deposit_index=pre.eth1_deposit_index,
        validators=pre.validators,
        balances=pre.balances,
        randao_mixes=pre.randao_mixes,
        slashings=pre.slashings,
        previous_epoch_participation=pre.previous_epoch_participation,
        current_epoch_participation=pre.current_epoch_participation,
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        inactivity_scores=pre.inactivity_scores,
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        latest_block_hash=pre.latest_block_hash,
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        historical_summaries=pre.historical_summaries,
        deposit_requests_start_index=pre.deposit_requests_start_index,
        deposit_balance_to_consume=pre.deposit_balance_to_consume,
        exit_balance_to_consume=pre.exit_balance_to_consume,
        earliest_exit_epoch=pre.earliest_exit_epoch,
        consolidation_balance_to_consume=pre.consolidation_balance_to_consume,
        earliest_consolidation_epoch=pre.earliest_consolidation_epoch,
        pending_deposits=pre.pending_deposits,
        pending_partial_withdrawals=pre.pending_partial_withdrawals,
        pending_consolidations=pre.pending_consolidations,
        proposer_lookahead=pre.proposer_lookahead,
        builders=pre.builders,
        next_withdrawal_builder_index=pre.next_withdrawal_builder_index,
        execution_payload_availability=pre.execution_payload_availability,
        builder_pending_payments=pre.builder_pending_payments,
        builder_pending_withdrawals=pre.builder_pending_withdrawals,
        latest_execution_payload_bid=pre.latest_execution_payload_bid,
        payload_expected_withdrawals=pre.payload_expected_withdrawals,
        ptc_window=pre.ptc_window,
        # [New in Trident]
        height=Height(1),
        # [New in Trident]
        height_entry_root=anchor_root,
        # [New in Trident]
        height_entry_slot=anchor_slot,
        # [New in Trident]
        non_justifiable=Boolean(False),
        # [New in Trident]
        height_participation=height_participation,
        # [New in Trident]
        latest_justified=HeightCheckpoint(height=Height(0), root=anchor_root),
        # [New in Trident]
        latest_finalized=HeightCheckpoint(height=Height(0), root=anchor_root),
    )

    return post
```
