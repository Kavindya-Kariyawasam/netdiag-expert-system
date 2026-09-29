"""
app.py - Web API layer for the NetDiag Expert System.
Exposes REST endpoints for forward chaining, backward chaining, and knowledge inspection.
"""
import uuid
from flask import Flask, request, jsonify, send_from_directory

from kb import FACTS, DIAGNOSES, RULES, label, validate_kb, RULE_PROVENANCE, CATEGORIES, PRESETS, INTERMEDIATE_LABELS
from engine import forward_chain, BackwardChainer, explain_how, explain_why_not, trace_to_text

app = Flask(__name__, static_folder="static", static_url_path="")

_SESSIONS = {}  # session_id -> dict(...)


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/facts")
def api_facts():
    """All askable facts, for building the forward-chaining checklist UI."""
    return jsonify([{"id": fid, "question": q} for fid, q in FACTS.items()])


@app.get("/api/goals")
def api_goals():
    """All diagnoses, for the backward-chaining goal picker."""
    return jsonify([{"id": gid, "title": title} for gid, (title, _rec) in DIAGNOSES.items()])


@app.get("/api/presets")
def api_presets():
    """Canonical test scenarios for one-click demonstration."""
    return jsonify(PRESETS)


@app.get("/api/categories")
def api_categories():
    """Diagnostic problem categories for guided backward triage."""
    return jsonify(CATEGORIES)


@app.get("/api/kb")
def api_kb():
    """Full rule listing with third-party citations."""
    return jsonify([{
        "id": r["id"],
        "text": r["text"],
        "conditions": r["conditions"],
        "conclusion": r["conclusion"],
        "provenance": RULE_PROVENANCE.get(r["id"])
    } for r in RULES])


# --------------------------------------------------------------------- #
# FORWARD CHAINING
# --------------------------------------------------------------------- #
@app.post("/api/forward")
def api_forward():
    """Data-driven consultation: derives all reachable diagnoses, intermediate hypotheses, and near matches."""
    body = request.get_json(force=True) or {}
    facts = body.get("facts") if isinstance(body.get("facts"), dict) else {}
    result = forward_chain(facts)

    diagnoses = []
    for d in result["diagnoses"]:
        title, recommendation = DIAGNOSES.get(d, (label(d), ""))
        diagnoses.append({
            "id": d, "title": title, "recommendation": recommendation,
            "how": explain_how(d, result["trace"], result["facts"]),
        })

    intermediate_findings = []
    for i in result.get("intermediate", []):
        intermediate_findings.append({
            "id": i,
            "title": INTERMEDIATE_LABELS.get(i, label(i)),
            "how": explain_how(i, result["trace"], result["facts"])
        })

    trace = [{"rule_id": f.rule_id, "text": f.text, "conclusion": label(f.conclusion)}
             for f in result["trace"]]

    return jsonify({
        "diagnoses": diagnoses,
        "trace": trace,
        "intermediate": intermediate_findings,
        "near_matches": result.get("near_matches", [])
    })


# --------------------------------------------------------------------- #
# BACKWARD CHAINING (interactive Q&A and guided triage)
# --------------------------------------------------------------------- #
@app.post("/api/backward/start")
def api_backward_start():
    """Body: {"goal": "...", "category": "...", "known_facts": {...}}"""
    body = request.get_json(force=True) or {}
    goal = body.get("goal")
    category = body.get("category")
    known_facts = body.get("known_facts") if isinstance(body.get("known_facts"), dict) else {}

    # Validate inputs
    if not category and not goal:
        return jsonify({"error": "Either 'category' or 'goal' must be provided."}), 400

    if category and category not in CATEGORIES:
        return jsonify({"error": f"Unknown category '{category}'."}), 400

    if not category and goal not in DIAGNOSES:
        return jsonify({"error": f"Unknown goal hypothesis '{goal}'."}), 400

    sid = str(uuid.uuid4())
    session = {
        "goal": goal,
        "category": category,
        "known": dict(known_facts),
        "pending_fact": None,
        "pending_rule": None
    }
    _SESSIONS[sid] = session

    return jsonify(_advance(sid))


@app.post("/api/backward/answer")
def api_backward_answer():
    """Body: {"session_id": "...", "answer": true|false|null}"""
    body = request.get_json(force=True) or {}
    sid = body.get("session_id")
    if not sid or sid not in _SESSIONS:
        return jsonify({"error": "Unknown or expired session"}), 404

    session = _SESSIONS[sid]
    fact = session.pop("pending_fact", None)
    if fact is not None:
        session["known"][fact] = body.get("answer")

    return jsonify(_advance(sid))


@app.get("/api/backward/why/<sid>")
def api_backward_why(sid):
    session = _SESSIONS.get(sid)
    if session is None or session.get("pending_fact") is None:
        return jsonify({"why": "There is no pending question to explain right now."})
    fact = session["pending_fact"]
    rule = session.get("pending_rule")
    chainer = BackwardChainer(session["known"], lambda f, r: None)
    why = chainer.why_ask(fact, rule) or "No rule reference found."
    return jsonify({"why": why})


def _advance(sid):
    """Drives one turn of backward chaining (either single hypothesis or category triage)."""
    session = _SESSIONS[sid]
    goal = session.get("goal")
    category = session.get("category")
    known = session["known"]

    asked_fact = {"value": None}
    asked_rule = {"value": None}

    def ask(fact, rule):
        asked_fact["value"] = fact
        asked_rule["value"] = rule
        raise _NeedInput()

    chainer = BackwardChainer(known, ask)

    # 1. Guided Category Triage Mode
    if category and category in CATEGORIES:
        goals = CATEGORIES[category]["diagnoses"]
        try:
            confirmed_goal = chainer.prove_first_of(goals)
        except _NeedInput:
            fact = asked_fact["value"]
            session["pending_fact"] = fact
            session["pending_rule"] = asked_rule["value"]
            return {
                "status": "question",
                "session_id": sid,
                "fact_id": fact,
                "question": FACTS.get(fact, fact),
            }

        if confirmed_goal:
            title, recommendation = DIAGNOSES.get(confirmed_goal, (label(confirmed_goal), ""))
            return {
                "status": "done",
                "session_id": sid,
                "goal": confirmed_goal,
                "goal_title": title,
                "result": True,
                "recommendation": recommendation,
                "trace": trace_to_text(chainer.trace),
                "how": explain_how(confirmed_goal, chainer.trace, chainer.known),
                "why_not": []
            }
        else:
            cat_info = CATEGORIES[category]
            return {
                "status": "done",
                "session_id": sid,
                "goal": category,
                "goal_title": cat_info["title"],
                "result": False,
                "recommendation": None,
                "trace": trace_to_text(chainer.trace),
                "how": [],
                "why_not": [
                    f"No hypothesis in '{cat_info['title']}' could be confirmed from the evidence provided.",
                    "All candidate rules in this category were evaluated and lacked matching conditions.",
                    "Tip: Try the Forward Chaining consultation or test another problem category."
                ]
            }

    # 2. Specific Single-Goal Mode
    try:
        result = chainer.prove(goal)
    except _NeedInput:
        fact = asked_fact["value"]
        session["pending_fact"] = fact
        session["pending_rule"] = asked_rule["value"]
        return {
            "status": "question",
            "session_id": sid,
            "fact_id": fact,
            "question": FACTS.get(fact, fact),
        }

    title, recommendation = DIAGNOSES.get(goal, (label(goal), ""))
    why_not = explain_why_not(goal, chainer.known) if not result else []

    return {
        "status": "done",
        "session_id": sid,
        "goal": goal,
        "goal_title": title,
        "result": result,
        "recommendation": recommendation if result else None,
        "trace": trace_to_text(chainer.trace),
        "how": explain_how(goal, chainer.trace, chainer.known) if result else [],
        "why_not": why_not
    }


class _NeedInput(Exception):
    pass


if __name__ == "__main__":
    issues = validate_kb()
    if issues:
        print("WARNING - KB issues detected:", issues)
    app.run(host="0.0.0.0", port=5000, debug=True)
