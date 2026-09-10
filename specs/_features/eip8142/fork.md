# EIP-8142 -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
- [Fork to EIP-8142](#fork-to-eip-8142)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the EIP-8142 upgrade.

## Configs

Warning: this configuration is not definitive.

| Name                   | Value                                 |
| ---------------------- | ------------------------------------- |
| `EIP8142_FORK_VERSION` | `Version('0xe8142000')`               |
| `EIP8142_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Fork to EIP-8142

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == EIP8142_FORK_EPOCH`, an irregular state
change is made to upgrade to EIP-8142.

The upgrade occurs after the completion of the inner loop of `process_slots`
that sets `state.slot` equal to `EIP8142_FORK_EPOCH * SLOTS_PER_EPOCH`.

*Note*: The payload of the last pre-fork block was delivered as a signed
envelope, so the upgraded bid carries an empty chunk commitment. No chunks are
ever validated against it, since chunks are only validated against the bid in
their own block.

```python
def upgrade_to_eip8142(pre: heze.BeaconState) -> BeaconState:
    epoch = heze.get_current_epoch(pre)
    latest_execution_payload_bid = ExecutionPayloadBid(
        parent_block_hash=pre.latest_execution_payload_bid.parent_block_hash,
        parent_block_root=pre.latest_execution_payload_bid.parent_block_root,
        block_hash=pre.latest_execution_payload_bid.block_hash,
        prev_randao=pre.latest_execution_payload_bid.prev_randao,
        fee_recipient=pre.latest_execution_payload_bid.fee_recipient,
        gas_limit=pre.latest_execution_payload_bid.gas_limit,
        builder_index=pre.latest_execution_payload_bid.builder_index,
        slot=pre.latest_execution_payload_bid.slot,
        value=pre.latest_execution_payload_bid.value,
        execution_payment=pre.latest_execution_payload_bid.execution_payment,
        blob_kzg_commitments=pre.latest_execution_payload_bid.blob_kzg_commitments,
        execution_requests_root=pre.latest_execution_payload_bid.execution_requests_root,
        inclusion_list_bits=pre.latest_execution_payload_bid.inclusion_list_bits,
        # [New in EIP8142]
        payload_chunks_root=Root(),
        # [New in EIP8142]
        payload_length=Uint64(0),
    )

    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [Modified in EIP8142]
            current_version=EIP8142_FORK_VERSION,
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
        # [Modified in EIP8142]
        latest_execution_payload_bid=latest_execution_payload_bid,
        payload_expected_withdrawals=pre.payload_expected_withdrawals,
        ptc_window=pre.ptc_window,
    )

    return post
```
