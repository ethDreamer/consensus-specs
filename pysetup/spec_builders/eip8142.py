from pysetup.constants import EIP8142

from .base import BaseSpecBuilder


class EIP8142SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8142

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
"""

    @classmethod
    def deprecate_containers(cls) -> set[str]:
        return {
            "SignedExecutionPayloadEnvelope",
            "SignedExecutionPayloadEnvelopes",
        }

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "get_execution_payload_envelope_signature",
            "upgrade_to_heze",
            "validate_execution_payload_envelope_gossip",
            "verify_execution_payload_envelope_signature",
        }
