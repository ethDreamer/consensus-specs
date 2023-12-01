# Optimistic Relay v3 -- Networking

This document contains the consensus-layer networking specification for v3 of the optimistic relay roadmap.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents

<!-- TOC -->

<!-- /TOC -->

## Modifications in Optimistic Relay v3

## Configuration



| Name                                       | Value                                            | Description                                                                  |
|--------------------------------------------|--------------------------------------------------|------------------------------------------------------------------------------|
| `VALIDATOR_REGISTRATION_TTL`               | `2**6` (= 64)                                    | Maximum number of seconds a validator registration message can be in flight  |
| `VALIDATOR_REGISTRATION_COOLDOWN_INTERVAL` | `2**11` (= 2048)                                 | Minimum number of seconds before validators can propagate a new registration |

## Containers

### New containers

#### `ValidatorRegistration`

```python
class ValidatorRegistration(Container):
    fee_recipient: ExecutionAddress
    gas_limit: uint64
    timestamp: uint64
    pubkey: BLSPubkey
```

#### `SignedValidatorRegistration`

```python
class SignedValidatorRegistration(Container):
    message: ValidatorRegistration
    signature: BLSSignature
```

#### `BuilderBid`

```python
class BuilderBid(Container):
    header: ExecutionPayloadHeader
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    value: uint256
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

#### `BuilderRegistration`

These are not sent on the p2p network, they are provided by relays upon request
```python
class BuilderRegistration(Container):
    pubkey: BLSPubkey
    collateral: uint256
```

### The gossip domain: gossipsub

Three new topics are added to support the gossip of validator registrations, builder bids, and signed builder bids.

#### Topics and messages

Topics follow the same specification as in prior upgrades. All existing topics remain stable.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `validator_registration` | `SignedValidatorRegistration` |
| `builder_bid` | `SignedBuilderBid` |
| `blinded_beacon_block` | `SignedBlindedBeaconBlock` |

##### Global topics

Optimistic relay v3 introduces three new global topics to facilitate communication between validators and builders.

###### `validator_registration`

This topic is used to propagate signed validator registration messages to the builder network.

The following validations MUST pass before forwarding the `signed_validator_registration` on the network:

- _[IGNORE]_ The `signed_validator_registration.message.timestamp` is not from the future (with a `MAXIMUM_CLOCK_DISPARITY` allowance).
- _[REJECT]_ The registration is from an active validator -- i.e. `signed_validator_registration.message.pubkey` belongs to a `validator` that satisfies `is_active_validator(validator, current_epoch)`
- _[IGNORE]_ The `signed_validator_registration.message.timestamp` + `VALIDATOR_REGISTRATION_TTL` is greater than the current wall-clock time (with a `MAXIMUM_CLOCK_DISPARITY` allowance). 
- _[REJECT]_ The signature is valid with respect to `signed_validator_registration.message.pubkey`
- _[IGNORE]_ The timestamp of this registration is at least `VALIDATOR_REGISTRATION_COOLDOWN_INTERVAL` seconds after the last valid registration from this validator -- i.e. `last_valid_registration.message.timestamp + VALIDATOR_REGISTRATION_COOLDOWN_INTERVAL <= signed_validator_registration.message.timestamp`

###### `builder_bid`

This topic is used to propagate signed builder bid messages to proposers.

The following validations MUST pass before forwarding the `signed_builder_bid` on the network:

- _[IGNORE]_ This builder is known to the beacon node -- i.e. `signed_builder_bid.message.pubkey` matches the pubkey of some [`BuilderRegistration`](#BuilderRegistration) retrieved from a relay.
- _[IGNORE]_ The relay has enough collateral to cover the bid -- i.e. `signed_builder_bid.message.value <= builder_registration.collateral`
- _[REJECT]_ The signature is valid with respect to `signed_builder_bid.message.pubkey`
- _[REJECT]_ The `signed_builder_bid.message.header` is valid with respect to the current state -- i.e. verify the following
    - `parent_hash`
    - `prev_randao`
    - `timestamp`
    - `block_number`
    - `withdrawals_root`
- _