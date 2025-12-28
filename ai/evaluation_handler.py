import sys
import json
import io
import contextlib

try:
    from .agent_manager import AgentManager
except Exception:
    from agent_manager import AgentManager


def extract_answer_from_result(result: dict) -> str:
    """
    Extract answer from result and ensure it's a clean string.
    """
    if not isinstance(result, dict):
        return str(result)
    
    # If the pipeline escalated or rejected the request and no explicit
    # final_response was provided, return a clear human-escalation message.
    status = result.get("status") if isinstance(result, dict) else None
    has_final = bool(result.get("final_response")) if isinstance(result, dict) else False
    if status in ("escalated", "rejected") and not has_final:
        # Try to surface target department or reason when available
        orientation = result.get("orientation") if isinstance(result, dict) else None
        reason = result.get("reason") if isinstance(result, dict) else None
        dept = None
        if isinstance(orientation, dict):
            dept = orientation.get("target_department")

        reason_text = ""
        if isinstance(reason, list):
            reason_text = "; ".join([str(r) for r in reason])
        elif isinstance(reason, str):
            reason_text = reason

        if dept:
            answer = f"La demande a été transmise à un agent humain ({dept}) pour prise en charge. {reason_text}".strip()
        else:
            answer = f"La demande a été transmise à un agent humain pour prise en charge. {reason_text}".strip()
        # If reason_text is empty, keep the message short
        if answer.endswith(".") and reason_text == "":
            answer = answer.rstrip()  # keep single sentence
    else:
        # Prefer final_response, then proposed_answer, then orientation summary or reason
        answer = None
        if "final_response" in result and result["final_response"]:
            answer = result["final_response"]
        elif "proposed_answer" in result and result["proposed_answer"]:
            answer = result["proposed_answer"]
        elif "orientation" in result and isinstance(result["orientation"], dict):
            answer = result["orientation"].get("summary", result.get("reason", ""))
        else:
            answer = result.get("reason", "") or ""
    
    # Ensure we have a string
    if not isinstance(answer, str):
        try:
            answer = json.dumps(answer, ensure_ascii=False)
        except Exception:
            answer = str(answer)
    
    # Clean up the string - remove excessive whitespace but preserve intentional formatting
    answer = answer.strip()
    
    return answer


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: python evaluation_handler.py <input_json_file>"
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        print(json.dumps({
            "error": f"File not found: {input_path}"
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(json.dumps({
            "error": f"Invalid JSON in input file: {e}"
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    questions = payload.get("Questions", [])
    if not isinstance(questions, list):
        print(json.dumps({
            "error": "Input JSON must contain a 'Questions' array"
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    manager = AgentManager()
    answers = []

    # Suppress stdout/stderr while processing tickets to ensure only the final
    # JSON is printed (automated evaluators rely on exact output).
    for q in questions:
        qid = q.get("id")
        query = q.get("query", "")

        # Suppress noisy prints/logs from the pipeline
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            try:
                result = manager.process_ticket(query)
            except Exception as e:
                result = {"status": "error", "reason": f"Processing error: {e}"}

        answer_text = extract_answer_from_result(result)
        
        answers.append({
            "id": qid,
            "answer": answer_text
        })

    output = {
        "Team": "TEAM 5",
        "Answers": answers
    }

    # Print only the required JSON to stdout with proper formatting
    # Using indent=2 for readability, ensure_ascii=False for Unicode support
    try:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    except Exception as e:
        # If somehow serialization fails, output error to stderr
        print(json.dumps({
            "error": f"Failed to serialize output: {e}"
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()