
# Optimistic Relay v3 -- Networking

This document contains the consensus-layer networking specification for v3 of the optimistic relay roadmap.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

  - [Modifications in Optimistic Relay v3](#modifications-in-optimistic-relay-v3)
    - [Configuration](#configuration)
    - [Containers](#containers)
    - [New containers](#new-containers)
      - [`ProposerAuction`](#proposerauction)
      - [`SignedProposerAuction`](#signedproposerauction)
      - [`BuilderBid`](#builderbid)
      - [`SignedBuilderBid`](#signedbuilderbid)
      - [`BlindedBeaconBlockBody`](#blindedbeaconblockbody)
      - [`BlindedBeaconBlock`](#blindedbeaconblock)
      - [`SignedBlindedBeaconBlock`](#signedblindedbeaconblock)
      - [`AcceptedBuilderBid`](#acceptedbuilderbid)
      - [`SignedAcceptedBuilderBid`](#signedacceptedbuilderbid)
    - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
      - [Topics and messages](#topics-and-messages)
        - [Global topics](#global-topics)
          - [`proposer_auction`](#proposer_auction)
          - [`builder_bid`](#builder_bid)
          - [`accepted_builder_bid`](#accepted_builder_bid)
      - [Transitioning the gossip](#transitioning-the-gossip)
- [Design decision rationale](#design-decision-rationale)
    - [Gossipsub](#gossipsub)
      - [Why is there no `parent_hash` in the proposer auction?](#why-is-there-no-parent_hash-in-the-proposer-auction)
      - [What's with this weird `ancestor_root` in the proposer auction?](#whats-with-this-weird-ancestor_root-in-the-proposer-auction)
      - [How do we expect the network to become aware of builder pubkeys in the beginning?](#how-do-we-expect-the-network-to-become-aware-of-builder-pubkeys-in-the-beginning)
      - [Why is the accepted builder bid double signed?](#why-is-the-accepted-builder-bid-double-signed)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in Optimistic Relay v3

### Configuration

| Name                                  | Value         | Description                                                                           |
|---------------------------------------|---------------|---------------------------------------------------------------------------------------|
| `MAX_PROPOSER_AUCTION_SLOT_LOOKAHEAD` | `2**4` (= 16) | Maximum number of slots between the current slot and a proposer auction target slot   |
| `MAX_PROPOSER_AUCTION_ANCESTOR_DISTANCE`| `2**1` (= 2)| Maximum number of slots behind the current slot of a proposer auction ancestor block  |
| `HALF_BUILDER_BID_WINDOW`             | `2**1` (= 2)  | Number of seconds away from the target slot that a builder bid can be gossiped        |
| `BUILDER_PUBKEY_RETENTION_PERIOD`     | `2**5` (= 32) | Number of epochs to retain a builder pubkey after the builder wins a proposer auction |
| `MAX_BUILDER_BIDS_PER_SLOT`           | `2**1` (=2)   | Maximum number of builder bids per slot                                               |

### Containers

### New containers

#### `ProposerAuction`

```python
class ProposerAuction(Container):
    fee_recipient: ExecutionAddress
    ancestor_root: Root
    gas_limit: uint64
    slot: Slot
    pubkey: BLSPubkey
```

#### `SignedProposerAuction`

```python
class SignedProposerAuction(Container):
    message: ProposerAuction
    signature: BLSSignature
```

#### `BuilderBid`

```python
class BuilderBid(Container):
    header: ExecutionPayloadHeader
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    value: uint256
    nonce: uint8
    pubkey: BLSPubkey
```

#### `SignedBuilderBid`

```python
class SignedBuilderBid(Container):
    message: BuilderBid
    signature: BLSSignature
```

#### `BlindedBeaconBlockBody`

```python
class BlindedBeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload_header: ExecutionPayloadHeader
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
```

#### `BlindedBeaconBlock`

```python
class BlindedBeaconBlock(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_root: Root
    state_root: Root
    body: BlindedBeaconBlockBody
```

#### `SignedBlindedBeaconBlock`

```python
class SignedBlindedBeaconBlock(Container):
    message: BlindedBeaconBlock
    signature: BLSSignature
```

#### `AcceptedBuilderBid`

```python
class AcceptedBuilderBid
    signed_blinded_block: SignedBlindedBeaconBlock
    builder_pubkey: BLSPubkey
```

#### `SignedAcceptedBuilderBid`

```python
class SignedAcceptedBuilderBid(Container):
    message: AcceptedBuilderBid
    signature: BLSSignature
```

### The gossip domain: gossipsub

Three new topics are added to support the gossip of proposer auctions, builder bids, and accepted builder bids.

#### Topics and messages

Topics follow the same specification as in prior upgrades. All existing topics remain stable.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `proposer_auction` | `SignedProposerAuction` |
| `builder_bid` | `SignedBuilderBid` |
| `accepted_builder_bid` | `SignedAcceptedBuilderBid` |

##### Global topics

Optimistic relay v3 introduces three new global topics to facilitate communication between validators and builders.

###### `proposer_auction`

This topic is used to propagate signed proposer auction messages to the builder network.

For convenience we define `current_slot` as the current slot with respect to the wall-clock time with a `MAXIMUM_CLOCK_DISPARITY` allowance. The following validations MUST pass before forwarding the `signed_proposer_auction` on the network:

- _[IGNORE]_ The target slot is greater than or equal to the `current_slot` -- i.e. `signed_proposer_auction.message.slot >= current_slot`.
- _[IGNORE]_ The target slot is no more than `MAX_PROPOSER_AUCTION_SLOT_LOOKAHEAD` ahead of the `current_slot` -- i.e. `signed_proposer_auction.message.slot <= current_slot + MAX_PROPOSER_AUCTION_SLOT_LOOKAHEAD`.
- _[IGNORE]_ This is the first `signed_proposer_auction` with valid signature received from this proposer for this target slot (defined by `signed_proposer_auction.message.slot`).
- _[REJECT]_ The public key is from a currently active validator -- i.e. `signed_proposer_auction.message.pubkey` belongs to a `validator` that satisfies `is_active_validator(validator, compute_epoch_at_slot(current_slot))`.
- _[REJECT]_ The signature, `signed_proposer_auction.signature`, is valid with respect to `signed_proposer_auction.message.pubkey`.
- _[IGNORE]_ The ancestor block (defined by `signed_proposer_auction.message.ancestor_root`) has been seen and has slot within `MAX_PROPOSER_AUCTION_ANCESTOR_DISTANCE` slots of the `current_slot` -- i.e. `current_slot >= ancestor_block.slot + MAX_PROPOSER_AUCTION_ANCESTOR_DISTANCE` (a client MAY queue signed proposer auctions for processing once the ancestor block is retrieved)
- _[REJECT]_ The ancestor block (defined by `signed_proposer_auction.message.ancestor_root`) passes validation
- _[REJECT]_ The public key belongs to a validator which is the expected proposer for the target slot, `signed_proposer_auction.message.slot`, in the context of the shuffling defined by the ancestor root, `signed_proposer_auction.message.ancestor_root`.

###### `builder_bid`

This topic is used to propagate signed builder bid messages to proposers.

The following validations MUST pass before forwarding the `signed_builder_bid` on the network:

- _[REJECT]_ The nonce is less than `MAX_BUILDER_BIDS_PER_SLOT` -- i.e. `signed_builder_bid.message.nonce < MAX_BUILDER_BIDS_PER_SLOT`
- _[IGNORE]_ The current wall-clock time is within `HALF_BUILDER_BID_WINDOW` seconds of the target slot's timestamp (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. `now - HALF_BUILDER_BID_WINDOW <= compute_timestamp_at_slot(state, signed_builder_bid.message.header.slot) <= now + HALF_BUILDER_BID_WINDOW`
- _[IGNORE]_ This is the first bid with valid signature received from this builder for this slot and nonce.
- _[IGNORE]_ This builder has won an auction within the last `BUILDER_PUBKEY_RETENTION_PERIOD` epochs -- i.e. this node has observed a valid `signed_accepted_builder_bid` for a block within `BUILDER_PUBKEY_RETENTION_PERIOD` epochs of the current epoch with respect to the wall-clock time where `signed_accepted_builder_bid.message.builder_pubkey == signed_builder_bid.message.pubkey`.
- _[REJECT]_ The signature, `signed_builder_bid.signature`, is valid with respect to `signed_builder_bid.message.pubkey`.

###### `accepted_builder_bid`

This topic is used to propagate signed accepted builder bids to builders and to allow the network to become aware of builders that win proposer auctions. When a proposer accepts a bid from a builder, regardless of whether they received the bid from RPC or gossip, the proposer MUST broadcast a `SignedAcceptedBuilderBid`.

The following validations MUST pass before forwarding the `signed_accepted_builder_bid` on the network (for convenience we define `signed_blinded_block = signed_accepted_builder_bid.message.signed_blinded_block` and `blinded_block = signed_blinded_block.message`):

- _[IGNORE]_ The `blinded_block` is for the current slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. `blinded_block.slot == current_slot`
- _[IGNORE]_ This is the first `signed_accepted_builder_bid` with valid signature received for the proposer for this slot.
- _[REJECT]_ The proposer signature, `signed_blinded_block.signature`, is valid with respect to the `blinded_block.proposer_index` pubkey.
- _[REJECT]_ The proposer signature, `signed_accepted_builder_bid.signature`, is valid with respect to the `blinded_block.proposer_index` pubkey.
- _[IGNORE]_ The block's parent (defined by `blinded_block.parent_root`) has been seen (a client MAY queue accepted builder bids for processing once the parent block is retrieved).
- _[REJECT]_ The block's parent (defined by `blinded_block.parent_root`) passes validation.
- _[REJECT]_ The block is from a higher slot than its parent.
- _[REJECT]_ The current `finalized_checkpoint` is an ancestor of `blinded_block` -- i.e. `get_checkpoint_block(store, block.parent_root, store.finalized_checkpoint.epoch) == store.finalized_checkpoint.root`.
- _[REJECT]_ The block is proposed by the expected `proposer_index` for the block's slot in the context of the current shuffling (defined by `parent_root`/`slot`). If the `proposer_index` cannot immediately be verified against the expected shuffling, the block MAY be queued for later processing while proposers for the block's branch are calculated -- in such a case do not `REJECT`, instead `IGNORE` this message.

When a valid `signed_accepted_builder_bid` is observed, clients MUST cache the builder pubkey (`signed_accepted_builder_bid.message.builder_pubkey`) for `BUILDER_PUBKEY_RETENTION_PERIOD` epochs. This cache is then used when validating `signed_builder_bid` messages.

#### Transitioning the gossip

See gossip transition details found in the [Altair document](../../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for this upgrade.

# Design decision rationale

### Gossipsub

#### Why is there no `parent_hash` in the proposer auction?

To minimize latency, we want proposers to be able to broadcast a `SignedProposerAuction` several slots before their actual proposal. This precludes including a `parent_hash` in the `SignedProposerAuction`. Note that because builders are able to broadcast up to `MAX_BUILDER_BIDS_PER_SLOT` bids for each slot, they are still able to speculate on more than one `parent_hash`. Proposers still retain the final choice on which `parent_hash` to choose, and under healthy chain conditions the choice is usually clear.

#### What's with this weird `ancestor_root` in the proposer auction?

Since there is no `parent_hash` included in the proposer auction, it is technically unnecessary to anchor proposer auctions to an upcoming block proposal. We anchor it anyway because this is a natural way to mitigate spam. We further mitigate spam by allowing proposers to only transmit one of these messages for a given proposal. Though typically stable within an epoch, the expected proposer for a given slot can change within a single block. Thus we anchor the proposal auction to an ancestor block with root `ancestor_root` for which the shuffling must produce the expected proposer. We avoid restricting the ancestor block to the current head so that nodes can wait longer for the ancestor block to propagate to all nodes before broadcasting their proposer auction.

#### How do we expect the network to become aware of builder pubkeys in the beginning?

When we first enable optimistic relay v3 auctions, we can bootstrap awareness of builder pubkeys from standard mev-boost auctions. This is why proposers are required to broadcast signed accepted builder bids even when they received the bid via RPC.

#### Why is the accepted builder bid double signed?

This is the only way to protect the `builder_pubkey` with the proposer's signature without changing any of the consensus data structures.
