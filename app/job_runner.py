"""
The "looping prompt" job system.

Flow:
1. Ask the LLM (via your existing router) to write code for the task.
2. Save it to a temp file and actually run it.
   - If you provided pytest tests -> run those tests against the code.
   - If not -> just run the file and check it doesn't crash.
3. If it fails, send the REAL error output back to the LLM and ask it to fix
   the code. Repeat until it passes or max_attempts is hit.

This only runs locally on your own machine for your own tasks — it does NOT
sandbox against malicious code, so don't expose this endpoint on the public
internet without adding real sandboxing (e.g. Docker, gVisor) first.
"""

import os
import re
import subprocess
import sys
import tempfile
import uuid

from app.router import call_llm

MAX_ATTEMPTS_DEFAULT = 5
EXEC_TIMEOUT_SECONDS = 15


def _extract_code(llm_text: str) -> str:
    """Pull code out of a ```python ... ``` block if present, else return as-is."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", llm_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return llm_text.strip()


def _run_plain(code: str) -> dict:
    """Just execute the file and see if it crashes."""
    work_dir = tempfile.mkdtemp(prefix="job_")
    solution_path = os.path.join(work_dir, "solution.py")
    with open(solution_path, "w", encoding="utf-8") as f:
        f.write(code)

    try:
        result = subprocess.run(
            [sys.executable, solution_path],
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            return {"passed": True, "output": result.stdout}
        return {"passed": False, "output": result.stdout, "error": result.stderr}
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": f"Timed out after {EXEC_TIMEOUT_SECONDS}s (possible infinite loop)"}


def _run_with_tests(code: str, tests: str) -> dict:
    """Write solution.py + test_solution.py, run pytest against them."""
    work_dir = tempfile.mkdtemp(prefix="job_")
    solution_path = os.path.join(work_dir, "solution.py")
    test_path = os.path.join(work_dir, "test_solution.py")

    with open(solution_path, "w", encoding="utf-8") as f:
        f.write(code)
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(tests)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-v"],
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT_SECONDS,
            cwd=work_dir,
        )
        if result.returncode == 0:
            return {"passed": True, "output": result.stdout}
        return {"passed": False, "output": result.stdout, "error": result.stderr}
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": f"Tests timed out after {EXEC_TIMEOUT_SECONDS}s"}


def run_job(
    task: str,
    tests: str | None = None,
    max_attempts: int = MAX_ATTEMPTS_DEFAULT,
    provider: str | None = None,
    file_context: str | None = None,
) -> dict:
    """
    task: plain-English description of what the code should do
    tests: optional pytest test code (must `from solution import ...`)
    max_attempts: how many fix-loops to allow before giving up
    provider: if set, only use this one provider (no failover)
    file_context: optional extracted text from uploaded files to reference

    Returns dict with: success, code, attempts (log), provider_used
    """
    job_id = str(uuid.uuid4())[:8]

    if tests:
        system_note = (
            "You are a coding assistant. Write ONLY Python code that solves the task. "
            "Your code will be saved as solution.py and imported by pytest tests. "
            "Respond with a single ```python code block, no explanations."
        )
    else:
        system_note = (
            "You are a coding assistant. Write ONLY a complete, runnable Python script "
            "that accomplishes the task. Respond with a single ```python code block, no explanations."
        )

    task_text = f"Task: {task}"
    if file_context:
        task_text += f"\n\nReference these uploaded files:\n{file_context}"
    if tests:
        task_text += f"\n\nThese tests must pass:\n```python\n{tests}\n```"

    messages = [
        {"role": "system", "content": system_note},
        {"role": "user", "content": task_text},
    ]

    attempt_log = []
    last_code = ""
    last_provider = None

    for attempt_num in range(1, max_attempts + 1):
        llm_result = call_llm(messages, max_tokens=1500, forced_provider=provider)
        code = _extract_code(llm_result["content"])
        last_code = code
        last_provider = llm_result["provider_used"]

        run_result = _run_with_tests(code, tests) if tests else _run_plain(code)

        attempt_log.append({
            "attempt": attempt_num,
            "provider": llm_result["provider_used"],
            "passed": run_result["passed"],
            "error": run_result.get("error"),
        })

        if run_result["passed"]:
            return {
                "job_id": job_id,
                "success": True,
                "code": code,
                "attempts_used": attempt_num,
                "attempt_log": attempt_log,
                "final_provider": last_provider,
            }

        # Feed the real error back to the LLM and ask for a fix
        messages.append({"role": "assistant", "content": llm_result["content"]})
        messages.append({
            "role": "user",
            "content": f"That code failed with this error:\n\n{run_result.get('error', 'unknown error')}\n\nFix the code and respond with the corrected ```python code block only.",
        })

    return {
        "job_id": job_id,
        "success": False,
        "code": last_code,
        "attempts_used": max_attempts,
        "attempt_log": attempt_log,
        "final_provider": last_provider,
    }