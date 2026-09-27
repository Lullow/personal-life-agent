# 0008 — How an answer is produced and graded

Status: accepted
Date: 2026-09-26

## Context

Every cell of the accuracy table is one model answering from what a strategy
recalled, and one model judging whether that answer is right. Only the
strategy may vary between rows. The prompt, the models and the judging rule
have to be fixed before the first strategy is measured; changing any of them
afterwards means measuring every strategy again.

The agent must not appear in the measured path (`CLAUDE.md`), so the answering
prompt is the harness's own and never comes from `prompts.py`.

LongMemEval publishes its grading in `src/evaluation/evaluate_qa.py`
(github.com/xiaowu0162/LongMemEval, MIT licence): one template per question
type, sent as a single user message to `gpt-4o-2024-08-06` at temperature 0 with
`max_tokens` 10. An answer counts as correct if the word "yes" appears in the
reply.

`LLMClient.chat_json` always sends a system prompt, always asks for JSON mode,
which needs the word "json" somewhere in the messages, and returns `None` on any
failure without saying why. The agent's `.env` names `openai/gpt-4o`, an alias
the provider can point at a newer model while the project is running.

## Decision

**Answering.** The model receives the strategy's `Retrieval.messages`
unchanged, followed by one user message:

```
Current date: {question_date}
Question: {question}
```

The system prompt is:

```
Below is your earlier conversation with the user. Answer the user's last
question using only that conversation. If it does not contain the answer, say
that you do not know. Reply with a JSON object: {"answer": "<your answer>"}.
```

**Grading.** The template for the question's type is copied verbatim from
`evaluate_qa.py` at commit `d0c699faf593726d96a6c75768e0fd2016d1feb8` and sent
as the only user message, filled with the question, `str(answer)` and the
model's answer. The system prompt is:

```
Reply with a JSON object: {"verdict": "yes"} or {"verdict": "no"}.
```

An answer is correct when `verdict` is `"yes"`. `answer` goes through `str()`,
because it is an integer in two questions. If the model's reply parses but
has no string `answer`, the grader is shown the whole reply as text: the model
did answer, only in the wrong shape. The copied templates keep LongMemEval's
copyright notice, as the MIT licence requires.

**Models.** `openai/gpt-4o-2024-08-06` through OpenRouter, for both answering
and grading, named by its dated id and never by an alias. Temperature is 0,
which is what `chat_json` sends. The model id is written into every result row.

**Failures.** A call that returns `None` is tried twice more. If it still fails,
the question is marked `error`, left out of the accuracy figure and counted
next to it. Errors are run again before any number goes into the report. A
failed call is never scored as a wrong answer. A question that still fails
after being run again is dropped from every strategy's figures, not only from
the one where it failed, so that every row is computed on the same questions.

## Consequences

Between strategies the grading is identical, which is the comparison that
matters. Against published LongMemEval numbers it differs in two ways, the
system prompt and JSON mode instead of looking for the word "yes", so
comparisons with the paper are approximate and have to say so.

One model answers and grades its own answers. The judge compares against a
reference answer, which limits how much that can matter, but the method
section names it as a limitation.

The answering prompt is not LongMemEval's own. Their reader gets the history as
one block of text with session dates; here it arrives as chat turns with no
dates, because `Retrieval.messages` carries none. Two things follow.

- The model is told the question date but not when anything in the history
  was said, so a phrase like "two weeks ago" cannot be placed in time. All 13
  time-worded questions among the 130 ("How long…", "When did I…") have their
  answer stated in the evidence itself: a duration, an age, or "Valentine's
  Day" for February 14th. None needs a session date, and the handicap is the
  same for every strategy.
- On a `knowledge-update` question, order is the only thing that tells the
  model which value is newer. That is the question M2's ordering record has to
  settle for `RetrievalMemory`, and it has to settle it within this record:
  showing dates for one strategy and not another would make the comparison
  about the dates.

The prompt shows `question_date` as the dataset gives it, clock time included,
as LongMemEval's reader does, although 0004 treats the question as asked at the
end of its day. The recalled messages carry no times, so nothing the model
sees contradicts it.

Because the history arrives as the model's own conversation rather than as
quoted data, a filler session that gives the assistant instructions ("act as a
Linux terminal") is an instruction in the conversation the model is continuing.
The pilot's answers are read by hand for this before any number is reported.

At $2.50 per million input tokens and $10 per million output tokens, an
answer call carrying the full budget costs about $0.02, and the M1 pilot, 20
answer calls and 20 grading calls, under $0.50.

If OpenRouter withdraws the dated model before the comparison is finished, it
cannot be finished as specified here. A new record supersedes this one, and
every strategy already measured is measured again.
