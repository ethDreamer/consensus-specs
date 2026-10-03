from pysetup.constants import TRIDENT

from .base import BaseSpecBuilder


class TridentSpecBuilder(BaseSpecBuilder):
    fork: str = TRIDENT

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        # Trident replaces the LMD-GHOST/FFG fork choice and the
        # fast-confirmation rule wholesale; the functions below read the
        # superseded store shape.
        return {
            "upgrade_to_heze",
            # FFG/LMD fork choice
            "on_attestation",
            "on_attester_slashing",
            "on_tick_per_slot",
            "update_checkpoints",
            "update_unrealized_checkpoints",
            "update_latest_messages",
            "update_proposer_boost_root",
            "store_target_checkpoint_state",
            "get_weight",
            "get_attestation_score",
            "get_equivocation_score",
            "get_proposer_score",
            "get_voting_source",
            "get_filtered_node_tree",
            "filter_node_tree",
            "get_pulled_up_head_state",
            "compute_pulled_up_tip",
            "should_apply_proposer_boost",
            "is_head_late",
            "is_head_weak",
            "is_parent_strong",
            "is_ffg_competitive",
            "is_finalization_ok",
            "is_valid_dependent_root",
            "record_block_timeliness",
            # Fast confirmation
            "get_fast_confirmation_store",
            "update_fast_confirmation_variables",
            "find_latest_confirmed_descendant",
            "get_latest_confirmed",
            "get_current_target",
            "get_current_target_score",
            "get_node_support_between_slots",
            "get_slot_committee",
            "get_previous_balance_source",
            "get_current_balance_source",
            "will_no_conflicting_checkpoint_be_justified",
            # Superseded node-weighted payload fork choice; payload status is
            # edge-committed in Trident (see fork-choice.md), and the envelope
            # and PTC handlers are inherited unchanged.
            "should_extend_payload",
            "prepare_execution_payload",
            # Gossip validations reading the superseded store shape
            "validate_beacon_block_gossip",
            "validate_beacon_attestation_gossip",
            "validate_beacon_aggregate_and_proof_gossip",
            "validate_attester_slashing_gossip",
            "validate_proposer_slashing_gossip",
            "validate_voluntary_exit_gossip",
            "validate_bls_to_execution_change_gossip",
            "validate_sync_committee_message_gossip",
            "validate_sync_committee_contribution_and_proof_gossip",
            # Transitive callers of the functions above
            "compute_adversarial_weight",
            "compute_empty_slot_support_discount",
            "is_one_confirmed",
            "is_confirmed_chain_safe",
            "compute_honest_ffg_support_for_current_target",
            "will_current_target_be_justified",
            "on_fast_confirmation",
            "get_node_children",
            "validate_on_attestation",
            "get_payload_status_tiebreaker",
            "verify_attestation_payload_status",
            "validate_proposer_preferences_gossip",
            "on_inclusion_list",
            "validate_inclusion_list_gossip",
            "get_adversarial_weight",
            "get_support_discount",
            "compute_safety_threshold",
        }
