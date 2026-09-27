"""Does the harness count the tokens the provider bills?

ADR 0006 counts cost with o200k_base on the harness's side, and requires one
real call to be checked by hand against the ``usage`` block OpenRouter returns
before the pilot. This script makes that call: the answer call for the first
pilot question, built by the harness's own functions, sent once through
``RecordingLLMClient`` to the dated model of ADR 0008. It prints the harness's
count next to the provider's.

What 0006 expects: the provider's input count is higher by a few tokens per
message, about 120 on a full answer call, because per-message framing is not
counted. The output count may differ slightly, because the harness counts the
JSON serialised again. Much more than that is a bug in the harness.

It also prints the model the provider says answered. If that is not the dated
id, the comparison cannot be run as 0008 specifies.

One call with about 8000 tokens of context: roughly two cents.

    .venv/bin/python scripts/check_token_count.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.longmemeval import (  # noqa: E402
    ANSWER_SYSTEM_PROMPT, MODEL, STRATEGIES, answer_messages, load_questions, real_client,
    recall_of,
)
from evals.verify_adr_numbers import SSU, TiktokenCounter, load_pinned  # noqa: E402
from life_agent.agent.recording import LLMCall, RecordingLLMClient  # noqa: E402


def main() -> int:
    data = {x["question_id"]: x for x in load_pinned()}
    qid = load_questions(1)[SSU][0]
    x = data[qid]
    counter = TiktokenCounter()
    retrieval, _, _ = recall_of(x, "clock", STRATEGIES["recent-turns"], counter)
    messages = answer_messages(x, retrieval)

    client = real_client()
    # chat_json drops the raw response and swallows errors; keep both.
    captured: dict = {}
    transport = client._post

    def recording_post(url: str, payload: dict) -> dict:
        try:
            captured["response"] = transport(url, payload)
        except urllib.error.HTTPError as exc:
            captured["error"] = f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}"
            raise
        except Exception as exc:
            captured["error"] = f"{type(exc).__name__}: {exc}"
            raise
        return captured["response"]

    client._post = recording_post  # type: ignore[method-assign]
    log: list[LLMCall] = []
    reply = RecordingLLMClient(client, label="answer", counter=counter, log=log).chat_json(
        ANSWER_SYSTEM_PROMPT, messages)
    call = log[0]

    print(f"question        {qid}: {x['question']}")
    print(f"gold answer     {x['answer']}")
    print(f"model answer    {reply}")
    if "error" in captured:
        print(f"\nthe call failed: {captured['error']}")
        return 1
    response = captured.get("response") or {}
    usage = response.get("usage") or {}
    print(f"\nmodel asked for {MODEL}")
    print(f"model answered  {response.get('model')}")
    print(f"provider        {response.get('provider', 'not reported')}")
    print(f"usage           {json.dumps(usage)}")
    if not usage or reply is None:
        print("\nno usage block or no parsed reply: nothing to compare")
        return 1

    n = 1 + len(messages)  # the system prompt counts as a message
    diff_in = usage["prompt_tokens"] - call.input_tokens
    diff_out = usage["completion_tokens"] - call.output_tokens
    print(f"\n{'':24s} {'harness':>9s} {'provider':>9s} {'diff':>6s}")
    print(f"{'input tokens':24s} {call.input_tokens:>9,} {usage['prompt_tokens']:>9,} {diff_in:>+6}")
    print(f"{'output tokens':24s} {call.output_tokens:>9,} {usage['completion_tokens']:>9,} {diff_out:>+6}")
    print(f"\nmessages, system prompt included: {n}")
    print(f"input difference per message:     {diff_in / n:+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
