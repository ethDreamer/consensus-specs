# Trident -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [`goldfish_vote`](#goldfish_vote)
    - [`trident_attestation_{subnet_id}`](#trident_attestation_subnet_id)
    - [`stabilization_aggregate`](#stabilization_aggregate)
    - [`finality_aggregate`](#finality_aggregate)
    - [`trident_slashing`](#trident_slashing)
  - [Modified validation helpers](#modified-validation-helpers)
    - [Modified `is_bid_compatible_with_head`](#modified-is_bid_compatible_with_head)
    - [Modified `validate_execution_payload_envelope_gossip`](#modified-validate_execution_payload_envelope_gossip)
    - [Modified `validate_payload_attestation_message_gossip`](#modified-validate_payload_attestation_message_gossip)
  - [Modified topics](#modified-topics)
    - [`beacon_block`](#beacon_block)

<!-- mdformat-toc end -->

## Introduction

This document describes the networking changes of Trident. The FFG attestation
topics (`beacon_attestation_{subnet_id}`, `beacon_aggregate_and_proof`,
`attester_slashing`) are retired; the topics below replace them. The Req/Resp
block sync protocols are unchanged.

Delivery within `DELTA_MS` after GST is the protocol's synchrony assumption, so
gossip forwarding of the objects below is mandatory, not best-effort: an honest
node forwards every accepted Goldfish vote and every accepted attestation
independently of block inclusion. Blocks are the secondary channel by which
recovering nodes refill their pools.

## The gossip domain: gossipsub

### Topics and messages

| Name                              | Message Type             |
| --------------------------------- | ------------------------ |
| `goldfish_vote`                   | `GoldfishVote`           |
| `trident_attestation_{subnet_id}` | `TridentAttestation`     |
| `stabilization_aggregate`         | `StabilizationAggregate` |
| `finality_aggregate`              | `FinalityAggregate`      |
| `trident_slashing`                | `TridentSlashing`        |

#### `goldfish_vote`

The following validations MUST pass before forwarding the `vote` on the network.

- _[IGNORE]_ `vote.data.slot` is the current slot or the previous slot (with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance).
- _[REJECT]_ The validator index is a member of the Goldfish committee of
  `vote.data.slot`.
- _[IGNORE]_ The store holds fewer than two distinct votes from this validator
  for `vote.data.slot`, and this vote is not a duplicate of a held vote.
- _[REJECT]_ The signature of `vote` is valid with respect to the validator's
  pubkey and `DOMAIN_GOLDFISH_VOTE`.

*Note*: A vote whose head block is unknown is still accepted and forwarded: a
vote is processed on receipt, whether or not the store holds its head, and
resolves later. Participation and equivocation are determined by cast votes,
regardless of resolution.

#### `trident_attestation_{subnet_id}`

The following validations MUST pass before forwarding the `attestation` on the
network.

- _[REJECT]_ `attestation.validator_index % ROUND_SUBNET_COUNT == subnet_id`.
- _[IGNORE]_ `attestation.stabilization.round` is within the expiry window:
  `max(0, current_round - SG_EXPIRY_WINDOW) <= round <= current_round` (with
  clock disparity allowance at round boundaries).
- _[REJECT]_ `attestation.stabilization.round == attestation.finality.round`.
- _[IGNORE]_ The store holds fewer than two attestations with distinct safe
  blocks from this validator for this round, and this attestation's safe block
  is not a duplicate: attestations differing only in their finality component
  are one vote, and the second of them is refused.
- _[REJECT]_ Both signatures are valid with respect to the validator's pubkey:
  `stabilization` under `DOMAIN_STABILIZATION_VOTE` and `finality` under
  `DOMAIN_FINALITY_VOTE`. Implementations SHOULD verify both in one same-signer
  batch.

*Note*: An attestation whose safe block is unknown is accepted and forwarded; it
resolves when the safe block arrives. An honest node forwards every accepted
attestation while its round is in the expiry window. Messages outside the window
need not be accepted or forwarded; old finality votes need not remain available
because validators can submit target and timeout votes again.

#### `stabilization_aggregate`

- _[IGNORE]_ `aggregate.data.round` is within the expiry window.
- _[REJECT]_ `aggregate.subnet_id < ROUND_SUBNET_COUNT`.
- _[REJECT]_ The aggregation bits match the subnet's member count, and at least
  one bit is set.
- _[REJECT]_ The aggregate signature is valid over the participating members'
  pubkeys.
- _[IGNORE]_ The aggregate adds at least one attestation row the node has not
  seen for this `(round, safe_root)` class.

#### `finality_aggregate`

The analogous validations with `DOMAIN_FINALITY_VOTE` over `FinalityData`
classes.

#### `trident_slashing`

- _[IGNORE]_ At least one of the referenced validators is slashable and not yet
  slashed.
- _[REJECT]_ `is_slashable_trident_evidence(evidence_1.data, evidence_2.data)`
  passes and both signatures are valid.

### Modified validation helpers

#### Modified `is_bid_compatible_with_head`

*Note*: Redefined over the root-valued Trident head. The payload-status arm uses
the root-based `should_build_on_full`.

```python
def is_bid_compatible_with_head(store: Store, bid: ExecutionPayloadBid) -> bool:
    """
    Check if ``bid`` is compatible with the head branch.
    """
    head_root = get_head(store)
    head_block = store.blocks[head_root]
    head_bid = head_block.body.signed_execution_payload_bid.message

    builds_on_parent_block = bid.parent_block_root == head_block.parent_root
    builds_on_parent_payload = bid.parent_block_hash == head_bid.parent_block_hash

    if builds_on_parent_block and builds_on_parent_payload:
        return True

    if bid.parent_block_root != head_root:
        return False

    builds_on_head_payload = bid.parent_block_hash == head_bid.block_hash

    if should_build_on_full(store, head_root):
        return builds_on_head_payload

    return builds_on_parent_payload
```

#### Modified `validate_execution_payload_envelope_gossip`

*Note*: Identical to the inherited validation, except that the finalized slot is
read from the Trident store's finalized block rather than from the retired
finalized checkpoint. Only the modified check is restated; all other checks are
unchanged.

```python
def validate_execution_payload_envelope_gossip(
    seen: Seen,
    store: Store,
    signed_execution_payload_envelope: SignedExecutionPayloadEnvelope,
) -> None:
    """
    Validate a ``SignedExecutionPayloadEnvelope`` for gossip propagation.
    Raises ``GossipIgnore`` or ``GossipReject`` on validation failure.
    """
    envelope = signed_execution_payload_envelope.message
    payload = envelope.payload
    block_root = envelope.beacon_block_root

    # [IGNORE] The node has not seen another valid envelope for this block root from this builder
    envelope_key = (block_root, envelope.builder_index)
    if envelope_key in seen.execution_payload_envelopes:
        raise GossipIgnore("already seen envelope for this block root from this builder")

    # [IGNORE] The envelope's block root has been seen (via gossip or non-gossip sources)
    if block_root not in store.blocks:
        raise GossipIgnore("envelope's block has not been seen")

    # [REJECT] The envelope's block passes validation
    if block_root not in store.block_states:
        raise GossipReject("envelope's block failed validation")

    state = store.block_states[block_root]

    # [IGNORE] The envelope is from a slot at or after the latest finalized slot
    # [Modified in Trident]
    finalized_slot = store.blocks[store.finalized_root].slot
    if payload.slot_number < finalized_slot:
        raise GossipIgnore("envelope is from a slot before the latest finalized slot")

    block = store.blocks[block_root]
    bid = block.body.signed_execution_payload_bid.message

    # [REJECT] The block's slot matches the payload's slot number
    if block.slot != payload.slot_number:
        raise GossipReject("block's slot does not match payload's slot number")

    # [REJECT] The envelope is from the builder committed to by the bid
    if envelope.builder_index != bid.builder_index:
        raise GossipReject("envelope's builder index does not match the bid's builder index")

    # [REJECT] The payload's block hash matches the bid's block hash
    if payload.block_hash != bid.block_hash:
        raise GossipReject("payload's block hash does not match the bid's block hash")

    # [REJECT] The envelope's execution requests root matches the bid's execution requests root
    if hash_tree_root(envelope.execution_requests) != bid.execution_requests_root:
        raise GossipReject("envelope's execution requests root does not match the bid's")

    # [REJECT] The execution request counts are within their limits
    verify_execution_requests_limits(envelope.execution_requests)

    # [REJECT] The number of withdrawals is within the limit
    if len(payload.withdrawals) > MAX_WITHDRAWALS_PER_PAYLOAD:
        raise GossipReject("too many withdrawals")

    # [REJECT] The envelope signature is valid
    if not verify_execution_payload_envelope_signature(state, signed_execution_payload_envelope):
        raise GossipReject("invalid envelope signature")

    # Mark this envelope as seen and store its payload
    seen.execution_payload_envelopes.add(envelope_key)
    seen.execution_payloads[payload.block_hash] = payload
```

#### Modified `validate_payload_attestation_message_gossip`

*Note*: Identical to the inherited validation, except that the head is the
root-valued Trident head.

```python
def validate_payload_attestation_message_gossip(
    seen: Seen,
    store: Store,
    payload_attestation_message: PayloadAttestationMessage,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a ``PayloadAttestationMessage`` for gossip propagation.
    Raises ``GossipIgnore`` or ``GossipReject`` on validation failure.
    """
    data = payload_attestation_message.data
    validator_index = payload_attestation_message.validator_index

    # [IGNORE] This is the first valid payload attestation from this validator index
    payload_attestation_key = (data.slot, validator_index)
    if payload_attestation_key in seen.payload_attestation_validators:
        raise GossipIgnore("already seen payload attestation from this validator")

    # [IGNORE] The payload attestation's slot is for the current slot
    if not is_current_slot(store, data.slot, current_time_ms):
        raise GossipIgnore("payload attestation is not for the current slot")

    # [IGNORE] The payload attestation's block has been seen (via gossip or non-gossip sources)
    if data.beacon_block_root not in store.blocks:
        raise GossipIgnore("payload attestation's block has not been seen")

    # [REJECT] The payload attestation's block passes validation
    if data.beacon_block_root not in store.block_states:
        raise GossipReject("payload attestation's block failed validation")

    # [IGNORE] The payload attestation's block is at the assigned slot
    if store.blocks[data.beacon_block_root].slot != data.slot:
        raise GossipIgnore("payload attestation's block is not at the assigned slot")

    # [Modified in Trident]
    state = store.block_states[get_head(store)]

    # [REJECT] The validator index is valid
    if validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    # [REJECT] The validator is a member of the payload timeliness committee
    if validator_index not in get_ptc(state, data.slot):
        raise GossipReject("validator is not in the payload timeliness committee")

    # [REJECT] The signature is valid
    validator = state.validators[validator_index]
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    if not bls.Verify(validator.pubkey, signing_root, payload_attestation_message.signature):
        raise GossipReject("invalid payload attestation signature")

    # Mark this payload_attestation as seen
    seen.payload_attestation_validators.add(payload_attestation_key)
```

### Modified topics

#### `beacon_block`

In addition to the inherited validations:

- _[REJECT]_ The block's legacy `attestations` and `attester_slashings` lists
  are empty.
- _[REJECT]_ Every included stabilization and finality aggregate has a round at
  most the round of the block's slot: a block may not include attestations from
  its own future.
- _[REJECT]_ Every included Goldfish aggregate has
  `data.slot + 1 == block.slot`, and its support bits mark a subset of its
  aggregation bits.
