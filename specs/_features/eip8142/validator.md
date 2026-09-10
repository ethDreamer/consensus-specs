# EIP-8142 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Signed execution payload bid](#signed-execution-payload-bid)
    - [Publishing self-built payloads](#publishing-self-built-payloads)
  - [Payload timeliness attestation](#payload-timeliness-attestation)
    - [Constructing the `PayloadAttestationMessage`](#constructing-the-payloadattestationmessage)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8142.

## Beacon chain responsibilities

### Block and sidecar proposal

#### Constructing the `BeaconBlockBody`

##### Signed execution payload bid

*Note*: The only change made to `signed_execution_payload_bid` is that the bid
also commits to the chunks of the payload, which the proposer verifies for
external bids and computes for self-builds.

- For self-builds, set `bid.payload_chunks_root` and `bid.payload_length` as
  described in the [honest builder](./builder.md) specification, using the
  `ExecutionPayload` and `ExecutionRequests` the proposer constructed.
- The `bid.payload_length` MUST satisfy
  `get_payload_chunk_count(bid.payload_length) <= MAX_PAYLOAD_CHUNKS`.

#### Publishing self-built payloads

After publishing the `SignedBeaconBlock`, a proposer that self-built the payload
broadcasts its chunks as an honest builder does, using
`get_execution_payload_chunks`, on the `execution_payload_chunk` global gossip
topic.

### Payload timeliness attestation

#### Constructing the `PayloadAttestationMessage`

*Note*: The only change made to `payload_attestation_message` is the source of
`data.payload_present`.

- If the validator has reconstructed the `ExecutionPayloadEnvelope` referencing
  the block with root `data.beacon_block_root` from its chunks, and held enough
  chunks to do so before `get_payload_due_ms()` milliseconds into the slot, set
  `data.payload_present` to `True`; otherwise, set `data.payload_present` to
  `False`.

*Note*: Validators do not need to check the full validity of the
`ExecutionPayload` contained in the reconstructed envelope, but the checks in
the [Networking](./p2p-interface.md) specification should pass for every chunk
used, and `reconstruct_execution_payload_envelope` should succeed.
