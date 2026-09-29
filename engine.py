"""
engine.py -- Inference Engine for the NetDiag Expert System
=============================================================

Implements, from scratch (no expert-system shell / no Prolog):
  - Forward chaining   (data-driven: facts in -> derive everything reachable)
  - Backward chaining  (goal-driven: pick a goal -> ask only what's needed)
  - Explanation facility:
        HOW  - "how did you reach this conclusion?" -> full rule-firing trace
        WHY  - "why are you asking me this?"        -> the rule that needs it

Facts are represented as a dict: fact_id -> True / False.
Unknown facts are simply absent from the dict (open-world within a
closed-world evaluation: a missing condition fact is treated as "not yet
established", never silently assumed true or false).
"""

from dataclasses import dataclass, field
from typing import Callable, Optional
from kb import RULES, FACTS, DIAGNOSES, INTERMEDIATE_LABELS, label


def _fact_and_polarity(condition: str):
    """'!foo' -> ('foo', False); 'foo' -> ('foo', True)."""
    if condition.startswith("!"):
        return condition[1:], False
    return condition, True


def _condition_satisfied(condition: str, known_facts: dict) -> Optional[bool]:
    """True/False if the condition's truth value is known, None if unknown."""
    fact, polarity = _fact_and_polarity(condition)
    if fact not in known_facts:
        return None
    return known_facts[fact] == polarity


@dataclass
class FiredRule:
    rule_id: str
    text: str
    conclusion: str
    conditions_used: list = field(default_factory=list)  # [(fact, value_used), ...]


# ---------------------------------------------------------------------------
# FORWARD CHAINING
# ---------------------------------------------------------------------------
def forward_chain(initial_facts: dict) -> dict:
    """
    Data-driven inference: starting from `initial_facts` (fact_id -> bool),
    repeatedly scan the rule base and fire any rule whose conditions are all
    satisfied, until a fixed point is reached (no more new facts derivable).

    Conflict resolution strategy: simple rule-order scan, fire-once-per-rule,
    repeat-until-no-change. This is deliberately simple and fully
    deterministic/order-independent for this KB (see tests), which matters
    more for an explainable teaching system than a fancier strategy like
    RETE or recency/specificity ordering would.

    Returns:
        {
          "facts": dict of all facts (given + derived),
          "trace": ordered list of FiredRule (the derivation history),
          "diagnoses": list of diagnosis fact_ids that were concluded
        }
    """
    known = dict(initial_facts)
    trace: list[FiredRule] = []
    fired_ids = set()

    changed = True
    while changed:
        changed = False
        for rule in RULES:
            if rule["id"] in fired_ids:
                continue
            values = [_condition_satisfied(c, known) for c in rule["conditions"]]
            if all(v is True for v in values):
                concl = rule["conclusion"]
                if known.get(concl) is not True:
                    known[concl] = True
                    fired_ids.add(rule["id"])
                    used = [(_fact_and_polarity(c)[0], known[_fact_and_polarity(c)[0]])
                            for c in rule["conditions"]]
                    trace.append(FiredRule(rule["id"], rule["text"], concl, used))
                    changed = True

    diagnoses = [f for f in known if known[f] is True and f in DIAGNOSES]
    intermediate = [f for f in known if known[f] is True and f in INTERMEDIATE_LABELS]

    # Calculate near matches (rules where at least 1 condition is met, none contradicted, <= 2 missing)
    near_matches = []
    for rule in RULES:
        if rule["id"] in fired_ids or rule["conclusion"] in diagnoses:
            continue
        satisfied = []
        missing = []
        contradicted = False
        for cond in rule["conditions"]:
            fact, polarity = _fact_and_polarity(cond)
            if fact in known:
                if known[fact] == polarity:
                    satisfied.append(fact)
                else:
                    contradicted = True
                    break
            else:
                missing.append({"fact": fact, "expected": polarity, "question": FACTS.get(fact, label(fact))})
        
        if not contradicted and len(satisfied) >= 1 and len(missing) <= 2:
            target = rule["conclusion"]
            title, rec = DIAGNOSES.get(target, (INTERMEDIATE_LABELS.get(target, label(target)), ""))
            near_matches.append({
                "rule_id": rule["id"],
                "rule_text": rule["text"],
                "target_id": target,
                "target_title": title,
                "conclusion_title": title,
                "recommendation": rec,
                "satisfied_count": len(satisfied),
                "total_count": len(rule["conditions"]),
                "match_ratio": f"{len(satisfied)}/{len(rule['conditions'])}",
                "satisfied_facts": [label(f) for f in satisfied],
                "missing_facts": missing,
                "missing": [m["question"] for m in missing]
            })

    near_matches.sort(key=lambda m: m["satisfied_count"] / m["total_count"], reverse=True)

    return {
        "facts": known,
        "trace": trace,
        "diagnoses": diagnoses,
        "intermediate": intermediate,
        "near_matches": near_matches
    }


# ---------------------------------------------------------------------------
# BACKWARD CHAINING
# ---------------------------------------------------------------------------
class BackwardChainer:
    """
    Goal-driven inference. Call `.prove(goal)` and it will:
      - return True/False immediately if already known,
      - otherwise look for rules concluding `goal` and recursively try to
        prove each rule's conditions, one AND-branch at a time,
      - when it needs an askable leaf fact it doesn't know yet, it calls
        `ask_callback(fact_id, asking_rule)` to obtain True/False from the
        user (or from a test double). If ask_callback returns None, that
        branch is treated as "cannot be established" and the engine moves
        on to the next candidate rule (backtracking).

    This mirrors classic goal-driven expert-system consultations (MYCIN-style):
    only the facts actually relevant to the chosen goal are ever asked.
    """

    def __init__(self, known_facts: dict, ask_callback: Callable[[str, Optional[dict]], Optional[bool]]):
        self.known = dict(known_facts)
        self.ask = ask_callback
        self.trace: list[FiredRule] = []
        self._in_progress: set[str] = set()  # cycle guard
        self._rule_stack: list[dict] = []

    def prove(self, goal: str) -> Optional[bool]:
        fact, polarity = _fact_and_polarity(goal)

        if fact in self.known:
            if self.known[fact] is None:
                return False
            return self.known[fact] == polarity

        if fact in self._in_progress:
            return None  # cycle guard: avoid infinite recursion
        self._in_progress.add(fact)

        result = self._prove_positive(fact)
        self._in_progress.discard(fact)

        if result is not None:
            self.known[fact] = result

        if result is None:
            return None
        return result == polarity

    def prove_first_of(self, goals: list[str]) -> Optional[str]:
        """
        Triage consultation: evaluates a sequence of candidate hypotheses in order.
        Returns the first goal confirmed True, or None if none could be confirmed.
        """
        for g in goals:
            if self.prove(g):
                return g
        return None

    def _prove_positive(self, fact: str) -> Optional[bool]:
        candidate_rules = [r for r in RULES if r["conclusion"] == fact]

        if not candidate_rules:
            # Leaf fact with no rule concluding it -> ask the user directly.
            if fact in FACTS:
                active_rule = self._rule_stack[-1] if self._rule_stack else None
                answer = self.ask(fact, active_rule)
                self.known[fact] = answer
                return answer
            return None  # no rule and not askable: genuinely unknown

        for rule in candidate_rules:
            self._rule_stack.append(rule)
            try:
                all_true = True
                used = []
                for cond in rule["conditions"]:
                    sub_fact, polarity = _fact_and_polarity(cond)
                    sub_result = self.prove(sub_fact if polarity else "!" + sub_fact)
                    if not sub_result:
                        all_true = False
                        break
                    used.append((sub_fact, self.known.get(sub_fact)))
                if all_true:
                    self.trace.append(FiredRule(rule["id"], rule["text"], fact, used))
                    return True
            finally:
                self._rule_stack.pop()
        return False

    def why_ask(self, fact: str, rule: Optional[dict] = None) -> Optional[str]:
        """Explanation for a pending question: which rule currently needs `fact`?"""
        target_rule = rule
        if target_rule is None:
            for r in RULES:
                if fact in [_fact_and_polarity(c)[0] for c in r["conditions"]]:
                    target_rule = r
                    break
        if target_rule:
            return (f"I'm asking this because rule {target_rule['id']} needs it to "
                    f"determine whether '{label(target_rule['conclusion'])}' holds:\n"
                    f"  {target_rule['text']}")
        return None


def explain_why_not(goal: str, known_facts: dict) -> list[str]:
    """
    Explains why a backward chaining hypothesis was NOT confirmed.
    Inspects rules concluding `goal` and identifies which conditions failed or remained unknown.
    """
    candidate_rules = [r for r in RULES if r["conclusion"] == goal]
    if not candidate_rules:
        return [f"No rules exist in the knowledge base that conclude '{label(goal)}'."]

    reasons = []
    for r in candidate_rules:
        satisfied = []
        contradicted = []
        unknown = []
        for cond in r["conditions"]:
            fact, polarity = _fact_and_polarity(cond)
            if fact in known_facts:
                if known_facts[fact] == polarity:
                    satisfied.append(f"'{label(fact)}' was {known_facts[fact]}")
                elif known_facts[fact] is None:
                    unknown.append(f"'{label(fact)}' was unknown")
                else:
                    contradicted.append(f"'{label(fact)}' was {known_facts[fact]} (rule needed {polarity})")
            else:
                unknown.append(f"'{label(fact)}' was unconfirmed")

        rule_desc = f"Rule {r['id']}"
        if contradicted:
            reasons.append(f"{rule_desc} failed because: {', '.join(contradicted)}.")
        elif unknown:
            reasons.append(f"{rule_desc} could not fire because required symptom(s) were unknown: {', '.join(unknown)}.")
        if satisfied:
            reasons.append(f"Symptoms matching this rule: {', '.join(satisfied)}.")

    return reasons


# ---------------------------------------------------------------------------
# EXPLANATION FACILITY ("HOW")
# ---------------------------------------------------------------------------
def explain_how(fact_id: str, trace: list[FiredRule], known_facts: dict, depth: int = 0) -> list[str]:
    """
    Build a human-readable, recursively-expanded explanation of how `fact_id`
    was concluded, by walking backward through the firing trace: the rule
    that concluded it, then the rules that concluded *its* conditions, etc.,
    down to the original user-supplied facts.
    """
    lines = []
    indent = "  " * depth
    firing = next((f for f in trace if f.conclusion == fact_id), None)

    if firing is None:
        if fact_id in known_facts:
            lines.append(f"{indent}- '{label(fact_id)}' was given directly by the user "
                         f"as {known_facts[fact_id]}.")
        return lines

    lines.append(f"{indent}- Rule {firing.rule_id} fired: {firing.text}")
    lines.append(f"{indent}  => concluding: '{label(fact_id)}'")
    for sub_fact, _val in firing.conditions_used:
        lines.extend(explain_how(sub_fact, trace, known_facts, depth + 1))
    return lines


def trace_to_text(trace: list[FiredRule]) -> str:
    if not trace:
        return "No rules fired."
    return "\n".join(f"{f.rule_id}: {f.text}" for f in trace)
