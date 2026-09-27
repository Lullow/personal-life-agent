"""Tests for the cost-measuring client wrapper.

The inner client and the token counter are both fakes: the counter counts
characters, so every expected figure can be read straight off the strings.
"""

import json

from life_agent.agent.recording import LLMCall, RecordingLLMClient


class CharCounter:
    def count(self, text: str) -> int:
        return len(text)


class FakeClient:
    def __init__(self, *replies):
        self._replies = list(replies)
        self.calls = []

    def chat_json(self, system_prompt, messages):
        self.calls.append((system_prompt, messages))
        return self._replies.pop(0)


MESSAGES = [
    {"role": "user", "content": "hej"},
    {"role": "assistant", "content": "hallå"},
]


def recording(inner, label="answer", log=None):
    log = [] if log is None else log
    return RecordingLLMClient(inner, label=label, counter=CharCounter(), log=log), log


def test_the_result_passes_through_unchanged():
    reply = {"answer": "Göteborg"}
    inner = FakeClient(reply)
    client, _ = recording(inner)

    assert client.chat_json("sys", MESSAGES) == reply
    assert inner.calls == [("sys", MESSAGES)]


def test_input_counts_the_system_prompt_and_every_message():
    client, log = recording(FakeClient({"answer": "x"}))

    client.chat_json("system", MESSAGES)

    assert log[0].input_tokens == len("system") + len("hej") + len("hallå")


def test_output_counts_the_json_serialised_again_without_escapes():
    reply = {"answer": "Göteborg"}
    client, log = recording(FakeClient(reply))

    client.chat_json("sys", MESSAGES)

    # ensure_ascii=False: "ö" is one character, not a six-character escape.
    assert log[0].output_tokens == len(json.dumps(reply, ensure_ascii=False))
    assert log[0].output_tokens < len(json.dumps(reply))


def test_a_failed_call_is_logged_with_no_output():
    client, log = recording(FakeClient(None))

    assert client.chat_json("sys", MESSAGES) is None
    assert log == [LLMCall(label="answer", input_tokens=3 + 3 + 5, output_tokens=0, failed=True)]


def test_clients_sharing_a_log_record_in_call_order():
    log: list[LLMCall] = []
    answer, _ = recording(FakeClient({"answer": "a"}, {"answer": "b"}), "answer", log)
    grade, _ = recording(FakeClient({"verdict": "yes"}), "grade", log)

    answer.chat_json("s", MESSAGES)
    grade.chat_json("s", MESSAGES)
    answer.chat_json("s", MESSAGES)

    assert [c.label for c in log] == ["answer", "grade", "answer"]
    assert not any(c.failed for c in log)
