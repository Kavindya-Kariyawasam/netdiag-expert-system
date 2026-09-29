"""
cli.py - Interactive Command-Line Interface for the NetDiag Expert System.

Allows running consultations, quick-test scenarios, and inspecting the Knowledge Base directly
from the terminal without needing a web browser.

Usage:
    python cli.py
"""
import sys
import os

from kb import (
    FACTS, DIAGNOSES, RULES, INTERMEDIATE_LABELS, label, validate_kb,
    SOURCES, CATEGORIES, PRESETS
)
from engine import (
    forward_chain, BackwardChainer, explain_how, explain_why_not, trace_to_text
)


def clear():
    print("\n" + "=" * 72 + "\n")


def print_header(title):
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def preset_scenarios_cli():
    print_header("QUICK-TEST DIAGNOSTIC SCENARIOS (Canonical Presets)")
    print("Select a pre-configured scenario to observe multi-step inference in action:\n")

    for idx, preset in enumerate(PRESETS, 1):
        print(f"  {idx:2d}. [{preset['category'].upper()}] {preset['name']}")
        print(f"      {preset['description']}")

    while True:
        choice = input(f"\nSelect scenario (1-{len(PRESETS)}), or 'q' to return: ").strip()
        if choice.lower() == 'q':
            return
        if choice.isdigit() and 1 <= int(choice) <= len(PRESETS):
            selected = PRESETS[int(choice) - 1]
            break
        print("Invalid selection.")

    print_header(f"RUNNING SCENARIO: {selected['name'].upper()}")
    print(f"Description: {selected['description']}\n")
    print("Simulated Symptoms Injected:")
    for fact_id, val in selected["facts"].items():
        print(f"  - {FACTS.get(fact_id, fact_id)} -> {val}")

    print("\n[Running forward-chaining inference engine...]")
    result = forward_chain(selected["facts"])

    print("\n" + "-" * 72)
    print("  INFERENCE RESULTS")
    print("-" * 72)

    if result["diagnoses"]:
        print(f"\nConfirmed {len(result['diagnoses'])} diagnosis(es):\n")
        for diag_id in result["diagnoses"]:
            title, recommendation = DIAGNOSES[diag_id]
            print(f"[*] DIAGNOSIS: {title.upper()}")
            print(f"    Actionable Remedy: {recommendation}")
            print("\n    Reasoning Explanation (HOW):")
            lines = explain_how(diag_id, result["trace"], result["facts"])
            for line in lines:
                print(f"    {line}")
            print()
    else:
        print("\nNo terminal diagnosis reached.")

    if result.get("intermediate"):
        print("Intermediate Hypotheses Derived:")
        for im in result["intermediate"]:
            print(f"  * {INTERMEDIATE_LABELS.get(im, im)}")
        print()

    print("-" * 72)
    print(f"Rule Firing Trace ({len(result['trace'])} rule(s) fired):")
    print(trace_to_text(result["trace"]))
    print("-" * 72)
    input("\nPress Enter to return to main menu...")


def forward_chaining_cli():
    print_header("FORWARD CHAINING CONSULTATION (Data-Driven)")
    print("Answer the questions below regarding your symptoms.")
    print("Enter 'y' for Yes, 'n' for No, or press Enter / '?' for Unknown.\n")

    user_facts = {}
    for fact_id, question in FACTS.items():
        while True:
            ans = input(f"[{fact_id}]\n  {question} (y/n/?): ").strip().lower()
            if ans in ('y', 'yes', 't', 'true'):
                user_facts[fact_id] = True
                break
            elif ans in ('n', 'no', 'f', 'false'):
                user_facts[fact_id] = False
                break
            elif ans in ('?', '', 'u', 'unknown'):
                break
            else:
                print("  Invalid input. Enter 'y', 'n', or press Enter for unknown.")

    print("\n[Inferring conclusions from supplied evidence...]")
    result = forward_chain(user_facts)

    print("\n" + "-" * 72)
    print("  CONSULTATION RESULTS")
    print("-" * 72)

    if result["diagnoses"]:
        print(f"\nConfirmed {len(result['diagnoses'])} Diagnosis(es):\n")
        for diag_id in result["diagnoses"]:
            title, recommendation = DIAGNOSES[diag_id]
            print(f"[*] DIAGNOSIS: {title.upper()}")
            print(f"    Actionable Remedy: {recommendation}")
            print("\n    Reasoning Explanation (HOW):")
            lines = explain_how(diag_id, result["trace"], result["facts"])
            for line in lines:
                print(f"    {line}")
            print()
    else:
        print("\nNo definitive final diagnosis reached with the current symptoms.")

    if result.get("intermediate"):
        print("\n[!] Intermediate Hypotheses Established:")
        for im in result["intermediate"]:
            print(f"    * {INTERMEDIATE_LABELS.get(im, im)}")

    if result.get("near_matches"):
        print("\n[?] Potential Diagnoses Under Investigation (Near Matches):")
        print("    The following rules matched some symptoms but need further checks:")
        for nm in result["near_matches"][:4]:
            print(f"    - {nm['target_title']} (Rule {nm['rule_id']})")
            print(f"      Matched {nm['satisfied_count']} of {nm['total_count']} conditions.")
            missing_prompts = [m["question"] for m in nm["missing_facts"]]
            print(f"      Needed to confirm: {' | '.join(missing_prompts)}")

    print("\n" + "-" * 72)
    print(f"Rule Firing Trace ({len(result['trace'])} rule(s) fired):")
    print(trace_to_text(result["trace"]))
    print("-" * 72)
    input("\nPress Enter to return to main menu...")


def backward_chaining_cli():
    print_header("BACKWARD CHAINING CONSULTATION (Goal-Driven)")
    print("Choose consultation mode:")
    print("  1. Guided Triage by Problem Category (Recommended: auto-tests candidate hypotheses)")
    print("  2. Test a Specific Suspected Diagnosis")

    sub_choice = input("\nEnter choice (1-2), or 'q' to cancel: ").strip()
    if sub_choice == 'q':
        return

    known_facts = {}

    def ask(fact_id, active_rule):
        while True:
            question = FACTS.get(fact_id, fact_id)
            ans = input(f"\n{question}\n[y: Yes | n: No | u: Don't Know | w: Why ask?]: ").strip().lower()
            if ans in ('y', 'yes', 't', 'true'):
                known_facts[fact_id] = True
                return True
            elif ans in ('n', 'no', 'f', 'false'):
                known_facts[fact_id] = False
                return False
            elif ans in ('u', 'unknown', 'dont know', 'd'):
                known_facts[fact_id] = None
                return None
            elif ans in ('w', 'why', '?'):
                why_text = chainer.why_ask(fact_id, active_rule)
                print("\n  [EXPLANATION FACILITY - WHY THIS QUESTION IS ASKED]")
                print(f"  {why_text}\n")
            else:
                print("  Please enter 'y', 'n', 'u', or 'w'.")

    chainer = BackwardChainer(known_facts, ask)

    if sub_choice == '1':
        print("\nSelect your general problem area:")
        cat_keys = list(CATEGORIES.keys())
        for idx, k in enumerate(cat_keys, 1):
            print(f"  {idx}. {CATEGORIES[k]['title']} - {CATEGORIES[k]['description']}")

        c_idx = input(f"\nSelect category (1-{len(cat_keys)}): ").strip()
        if not (c_idx.isdigit() and 1 <= int(c_idx) <= len(cat_keys)):
            print("Invalid category.")
            return
        selected_cat = cat_keys[int(c_idx) - 1]
        cat_info = CATEGORIES[selected_cat]
        print(f"\nTarget Domain: {cat_info['title'].upper()}")
        print("The system will now evaluate candidate hypotheses in this domain.\n")

        confirmed_goal = chainer.prove_first_of(cat_info["diagnoses"])

        print_header("TRIAGE CONSULTATION RESULT")
        if confirmed_goal:
            title, recommendation = DIAGNOSES[confirmed_goal]
            print(f"[*] RESULT: {title.upper()} is CONFIRMED.")
            print(f"    Actionable Remedy: {recommendation}")
            print("\n    Reasoning Explanation (HOW):")
            lines = explain_how(confirmed_goal, chainer.trace, chainer.known)
            for line in lines:
                print(f"    {line}")
        else:
            print(f"[*] RESULT: No hypothesis in '{cat_info['title']}' could be confirmed.")
            print("    The supplied symptoms ruled out all candidate causes in this domain.")
            print("\n    Rules evaluated:")
            print(f"    {trace_to_text(chainer.trace)}")

    else:
        goal_list = list(DIAGNOSES.keys())
        for idx, gid in enumerate(goal_list, 1):
            title, _ = DIAGNOSES[gid]
            print(f"  {idx:2d}. {title} ({gid})")

        choice = input(f"\nEnter choice (1-{len(goal_list)}): ").strip()
        if not (choice.isdigit() and 1 <= int(choice) <= len(goal_list)):
            print("Invalid choice.")
            return
        selected_goal = goal_list[int(choice) - 1]
        goal_title, recommendation = DIAGNOSES[selected_goal]

        print(f"\nTarget Hypothesis: {goal_title.upper()}")
        print("Evaluating proof tree for this hypothesis...\n")
        confirmed = chainer.prove(selected_goal)

        print_header("BACKWARD CHAINING RESULT")
        if confirmed:
            print(f"[*] RESULT: {goal_title.upper()} is CONFIRMED.")
            print(f"    Actionable Remedy: {recommendation}")
            print("\n    Reasoning Explanation (HOW):")
            lines = explain_how(selected_goal, chainer.trace, chainer.known)
            for line in lines:
                print(f"    {line}")
        else:
            print(f"[*] RESULT: {goal_title.upper()} is NOT CONFIRMED.")
            print("\n    Why this hypothesis was ruled out:")
            reasons = explain_why_not(selected_goal, chainer.known)
            for r in reasons:
                print(f"    - {r}")

    input("\nPress Enter to return to main menu...")


def inspect_kb_cli():
    print_header("KNOWLEDGE BASE INSPECTOR")
    print(f"Total Rules: {len(RULES)} | Total Askable Facts: {len(FACTS)}")
    print(f"Intermediate Hypotheses: {len(INTERMEDIATE_LABELS)} | Diagnoses: {len(DIAGNOSES)}\n")

    for rule in RULES:
        print(f"[*] Rule {rule['id']}:")
        print(f"    Logic: IF {' AND '.join(rule['conditions'])} THEN {rule['conclusion']}")
        print(f"    Plain: {rule['text']}")
        source = SOURCES.get(rule['id'], "Standard IT Diagnostic Reference")
        print(f"    Source: {source}")
        print()

    input("Press Enter to return to main menu...")


def run_tests_cli():
    print_header("RUNNING AUTOMATED TEST SUITE")
    import pytest
    pytest.main(["-v", os.path.join(os.path.dirname(__file__), "tests")])
    input("\nPress Enter to return to main menu...")


def main():
    issues = validate_kb()
    if issues:
        print("WARNING: Knowledge Base integrity issues detected:", issues)

    while True:
        clear()
        print("=" * 72)
        print("       NetDiag Expert System - IT & Network Troubleshooting")
        print("=" * 72)
        print("  1. Quick-Test Diagnostic Scenarios (Canonical Presets - Instant Proofs)")
        print("  2. Forward-Chaining Consultation (Data-Driven: All Symptoms)")
        print("  3. Backward-Chaining Consultation (Goal-Driven: Targeted Q&A or Triage)")
        print("  4. Inspect Knowledge Base (View all 28 rules & citations)")
        print("  5. Run Automated Test Suite (pytest 36 tests)")
        print("  6. Exit")
        print("=" * 72)

        choice = input("Select an option (1-6): ").strip()
        if choice == '1':
            preset_scenarios_cli()
        elif choice == '2':
            forward_chaining_cli()
        elif choice == '3':
            backward_chaining_cli()
        elif choice == '4':
            inspect_kb_cli()
        elif choice == '5':
            run_tests_cli()
        elif choice == '6':
            print("\nExiting NetDiag Expert System. Goodbye!\n")
            sys.exit(0)
        else:
            print("Invalid selection. Please choose 1 to 6.")


if __name__ == "__main__":
    main()
