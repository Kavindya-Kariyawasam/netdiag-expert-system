"""
test_engine.py -- Test suite for the NetDiag inference engine.

Run with:  pytest -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from kb import RULES, FACTS, DIAGNOSES, INTERMEDIATE_LABELS, validate_kb, CATEGORIES, PRESETS
from engine import forward_chain, BackwardChainer, explain_how, explain_why_not, trace_to_text


# ---------------------------------------------------------------------------
# 1. KNOWLEDGE BASE INTEGRITY
# ---------------------------------------------------------------------------

def test_kb_has_minimum_facts_and_rules():
    assert len(FACTS) + len(INTERMEDIATE_LABELS) + len(DIAGNOSES) >= 20
    assert len(RULES) >= 20


def test_kb_no_dangling_references():
    assert validate_kb() == []


def test_every_diagnosis_has_recommendation_text():
    for key, (title, recommendation) in DIAGNOSES.items():
        assert title.strip() != ""
        assert recommendation.strip() != ""


def test_every_rule_conclusion_is_declared_fact():
    known = set(FACTS) | set(INTERMEDIATE_LABELS) | set(DIAGNOSES)
    for rule in RULES:
        assert rule["conclusion"] in known, f"{rule['id']} concludes undeclared fact"


# ---------------------------------------------------------------------------
# 2. FORWARD CHAINING -- one positive test per representative diagnostic path
# ---------------------------------------------------------------------------

def test_forward_router_powered_off():
    result = forward_chain({"no_internet_access": True, "power_light_on": False})
    assert "router_powered_off" in result["diagnoses"]


def test_forward_router_hardware_fault_multi_level():
    """Exercises 2-level chaining: suspect_router_fault -> router_hardware_fault."""
    result = forward_chain({
        "no_internet_access": True,
        "power_light_on": True,
        "can_ping_router": False,
        "router_recently_rebooted": True,
    })
    assert "router_hardware_fault" in result["diagnoses"]
    # the intermediate hypothesis must also have been derived
    assert result["facts"].get("suspect_router_fault") is True


def test_forward_isp_outage_requires_multiple_devices():
    result = forward_chain({
        "no_internet_access": True,
        "can_ping_router": True,
        "can_ping_external_ip": False,
        "multiple_devices_affected": True,
    })
    assert "isp_outage" in result["diagnoses"]


def test_forward_single_device_local_config_not_isp():
    """Same as above but single device -> must NOT conclude isp_outage."""
    result = forward_chain({
        "no_internet_access": True,
        "can_ping_router": True,
        "can_ping_external_ip": False,
        "multiple_devices_affected": False,
    })
    assert "isp_outage" not in result["diagnoses"]
    assert result["facts"].get("suspect_local_config_issue") is True


def test_forward_dns_failure_three_level_chain():
    """can_ping_external_ip(T) + can_resolve_dns(F) -> suspect_dns_issue
       -> + browser_dns_error_shown(T) -> dns_failure"""
    result = forward_chain({
        "can_ping_external_ip": True,
        "can_resolve_dns": False,
        "browser_dns_error_shown": True,
    })
    assert "dns_failure" in result["diagnoses"]


def test_forward_vpn_dns_conflict_alternate_branch():
    result = forward_chain({
        "can_ping_external_ip": True,
        "can_resolve_dns": False,
        "vpn_active": True,
        "browser_dns_error_shown": False,
    })
    assert "vpn_dns_conflict" in result["diagnoses"]
    assert "dns_failure" not in result["diagnoses"]


def test_forward_malware_infection():
    result = forward_chain({"system_slow": True, "malware_scan_flagged": True})
    assert "malware_infection" in result["diagnoses"]


def test_forward_new_software_resource_conflict_chain():
    result = forward_chain({
        "system_slow": True,
        "high_cpu_usage": True,
        "malware_scan_flagged": False,
        "new_software_installed": True,
    })
    assert "new_software_resource_conflict" in result["diagnoses"]


def test_forward_failing_disk_requires_both_conditions():
    result = forward_chain({"system_slow": True, "high_disk_usage": True, "disk_check_errors": False})
    assert "failing_disk" not in result["diagnoses"]
    result2 = forward_chain({"system_slow": True, "high_disk_usage": True, "disk_check_errors": True})
    assert "failing_disk" in result2["diagnoses"]


def test_forward_thermal_throttling():
    result = forward_chain({"overheating_detected": True, "high_cpu_usage": True})
    assert "thermal_throttling" in result["diagnoses"]


def test_forward_blue_screen_multiple_candidate_causes_can_coexist():
    """If both outdated driver AND overheating are true, both diagnoses should fire --
    the system doesn't hide alternative explanations."""
    result = forward_chain({
        "blue_screen_recently": True,
        "driver_outdated": True,
        "overheating_detected": True,
    })
    assert "driver_crash" in result["diagnoses"]
    assert "hardware_overheating_crash" in result["diagnoses"]


def test_forward_no_symptoms_yields_no_diagnosis():
    result = forward_chain({"no_internet_access": False, "system_slow": False})
    assert result["diagnoses"] == []


def test_forward_empty_input_does_not_crash():
    result = forward_chain({})
    assert result["diagnoses"] == []
    assert result["trace"] == []


def test_forward_unknown_facts_do_not_crash_or_falsely_fire():
    """Facts never mentioned at all must not be treated as True or False."""
    result = forward_chain({"no_internet_access": True})  # power_light_on unknown
    assert "router_powered_off" not in result["diagnoses"]


def test_forward_order_independence():
    facts_a = {"no_internet_access": True, "power_light_on": False}
    facts_b = {"power_light_on": False, "no_internet_access": True}
    r1 = forward_chain(facts_a)
    r2 = forward_chain(facts_b)
    assert r1["diagnoses"] == r2["diagnoses"]


def test_forward_terminates_fixed_point_no_infinite_loop():
    """All rules true at once must still terminate (regression guard)."""
    all_true = {f: True for f in FACTS}
    result = forward_chain(all_true)  # should simply return, not hang
    assert isinstance(result["diagnoses"], list)


# ---------------------------------------------------------------------------
# 3. BACKWARD CHAINING
# ---------------------------------------------------------------------------

def test_backward_proves_goal_true_with_scripted_answers():
    answers = {"no_internet_access": True, "power_light_on": False}
    chainer = BackwardChainer({}, lambda fact, rule: answers.get(fact))
    assert chainer.prove("router_powered_off") is True


def test_backward_returns_false_when_conditions_fail():
    answers = {"no_internet_access": True, "power_light_on": True}
    chainer = BackwardChainer({}, lambda fact, rule: answers.get(fact))
    assert chainer.prove("router_powered_off") is False


def test_backward_only_asks_relevant_questions():
    """Backward chaining for router_powered_off should never need to ask
    about, say, disk_check_errors -- proving goal-directedness."""
    asked = []
    answers = {"no_internet_access": True, "power_light_on": False}

    def ask(fact, rule):
        asked.append(fact)
        return answers.get(fact)

    chainer = BackwardChainer({}, ask)
    chainer.prove("router_powered_off")
    assert "disk_check_errors" not in asked
    assert "no_internet_access" in asked and "power_light_on" in asked


def test_backward_multi_level_chain_router_hardware_fault():
    answers = {
        "no_internet_access": True,
        "power_light_on": True,
        "can_ping_router": False,
        "router_recently_rebooted": True,
    }
    chainer = BackwardChainer({}, lambda fact, rule: answers.get(fact))
    assert chainer.prove("router_hardware_fault") is True
    # intermediate fact should have been cached as known too
    assert chainer.known.get("suspect_router_fault") is True


def test_backward_uses_already_known_facts_without_asking():
    asked = []
    chainer = BackwardChainer({"no_internet_access": True, "power_light_on": False},
                               lambda fact, rule: asked.append(fact) or None)
    result = chainer.prove("router_powered_off")
    assert result is True
    assert asked == []  # nothing needed to be asked; both facts already known


def test_backward_unanswerable_question_yields_none_not_crash():
    chainer = BackwardChainer({}, lambda fact, rule: None)  # user always "don't know"
    result = chainer.prove("router_powered_off")
    assert result is False  # cannot establish -> rule fails to fire


def test_backward_why_explanation_references_correct_rule():
    chainer = BackwardChainer({}, lambda fact, rule: None)
    explanation = chainer.why_ask("power_light_on")
    assert explanation is not None
    assert "R1" in explanation


def test_backward_active_rule_passed_to_ask_callback():
    received_rules = []

    def ask(fact, rule):
        received_rules.append((fact, rule["id"] if rule else None))
        return True

    chainer = BackwardChainer({}, ask)
    chainer.prove("router_powered_off")
    # Both leaf facts should receive rule R1 as the asking rule
    assert ("no_internet_access", "R1") in received_rules
    assert ("power_light_on", "R1") in received_rules


def test_backward_dont_know_recorded_as_none_and_not_reasked():
    asked = []

    def ask(fact, rule):
        asked.append(fact)
        return None  # User doesn't know

    chainer = BackwardChainer({"no_internet_access": None}, ask)
    res = chainer.prove("router_powered_off")
    assert res is False
    assert "no_internet_access" not in asked  # Already recorded as unknown, must not re-ask



# ---------------------------------------------------------------------------
# 4. EXPLANATION FACILITY ("HOW")
# ---------------------------------------------------------------------------

def test_explain_how_traces_multi_level_derivation():
    result = forward_chain({
        "no_internet_access": True,
        "power_light_on": True,
        "can_ping_router": False,
        "router_recently_rebooted": True,
    })
    lines = explain_how("router_hardware_fault", result["trace"], result["facts"])
    text = "\n".join(lines)
    assert "R3" in text
    assert "R2" in text  # the deeper rule that established suspect_router_fault
    assert "given directly by the user" in text


def test_trace_to_text_empty_trace():
    assert trace_to_text([]) == "No rules fired."


def test_trace_to_text_nonempty():
    result = forward_chain({"no_internet_access": True, "power_light_on": False})
    text = trace_to_text(result["trace"])
    assert "R1" in text


def test_forward_chain_near_matches():
    # Only one symptom given: should find near matches rather than dead end
    result = forward_chain({"no_internet_access": True})
    assert result["diagnoses"] == []
    assert len(result["near_matches"]) > 0
    # Rule R1 should be a top near match (needs only power_light_on=False)
    r1_match = next((m for m in result["near_matches"] if m["rule_id"] == "R1"), None)
    assert r1_match is not None
    assert r1_match["target_id"] == "router_powered_off"


def test_forward_chain_intermediate_findings():
    # Establishes intermediate hypothesis without final diagnosis
    result = forward_chain({
        "no_internet_access": True,
        "power_light_on": True,
        "can_ping_router": False
    })
    assert "suspect_router_fault" in result["intermediate"]
    assert "router_hardware_fault" not in result["diagnoses"]  # Needs reboot fact


def test_backward_prove_first_of_triage():
    answers = {
        "no_internet_access": True,
        "power_light_on": True,
        "can_ping_router": False,
        "router_recently_rebooted": True
    }
    chainer = BackwardChainer({}, lambda fact, rule: answers.get(fact))
    # Triage across multiple goals: first goal router_powered_off fails (power is on), second goal router_hardware_fault succeeds
    goals = ["router_powered_off", "router_hardware_fault", "isp_outage"]
    confirmed = chainer.prove_first_of(goals)
    assert confirmed == "router_hardware_fault"


def test_explain_why_not():
    # Goal failed because power light is ON instead of OFF
    reasons = explain_why_not("router_powered_off", {"no_internet_access": True, "power_light_on": True})
    text = "\n".join(reasons)
    assert "Rule R1" in text
    assert "power light" in text

