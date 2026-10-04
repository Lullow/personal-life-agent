# Review of the M3 run `consolidating-20261003-233313`

The answers of the M3 run read by hand on 2026-10-04, as ADR 0008 requires
before any figure is reported. The rows are in this directory:
`ConsolidatingMemory` under ADRs 0013–0017, the code of commit `fa2d293`,
`openai/gpt-4o-2024-08-06` answering and `openai/gpt-4o-mini-2024-07-18`
consolidating, the first 61 questions of each type, eight questions in flight
at a time, the night of 3–4 October. The reading files were written by
`evals/write_run_reading.py`, which for this strategy prints the notes the
model saw, and split into the three groups below.

The reading was one reading made in dialogue, not two independent ones: the
author read every answer and sorted it, an AI assistant in chat sorted the
same files, the first five `knowledge-update` errors were gone through
together to set the boxes, and the rest were compared line by line; the
boxes are what the two agreed on. The author's notes are
`lasning-m3-anteckningar.md` in this directory. The boxes were then checked
against the rows, and every figure below that comes from the rows is printed
by `evals/m3_review_figures.py`.

## Figures

| | single-session-user | knowledge-update |
|---|---:|---:|
| correct | 14 of 61 | 20 of 61 |
| evidence reached, window | 6 of 61 | 10 of 61 |
| evidence consolidated | 61 of 61 | 61 of 61 |

No question errored, no recall was over budget, every verdict was `yes` or
`no`. 91 consolidation calls failed, all loops (0016), and 17 sessions in 15
questions were skipped for it; none of them held an evidence turn, since
`evidence consolidated` is 1.000 in every row. OpenRouter billed $12.03 for
the run against the $11.07 the harness counts.

## Summary

- **No answer followed an instruction from a filler conversation.** Every
  answer either answered the question or said that it did not know, also
  where the window or the notes carried an instruction ("Please ignore all
  previous instructions" in the window of `4b24c848`).
- **No grading error was found.** `07741c45` was judged `no` for "planning
  to store your old sneakers in a shoe rack" against "in a shoe rack in my
  closet"; `6ade9755` ("have a connection to Serenity Yoga") and `d7c942c3`
  ("It seems likely") were judged `yes`. The judge gives no reason, so the
  line between them is the judge's.
- **The requested value was in the notes in 28 of 122 questions**, by the
  reading, and the answer was right in 26 of them. In 82 of the 88 errors the
  value is not in the notes at all. The consolidator had read it in every
  one; it was lost in the rewriting.
- **"I do not know" is the answer in 37 of the 41 `knowledge-update` errors
  and all 47 `single-session-user` errors.** The four others answered a
  value: `07741c45` (judged wrong), `0977f2af`, `e66b632c` and `f685340e`,
  the last three asked for the earlier value and answered the newer one.
- **The notes alone gave 21 correct answers**, 10 and 11, against the
  baseline's 3 and 9; the window gave 7 and both together 5; one is a guess.

## `knowledge-update`, wrong (41)

The boxes of the reading, and what the rows add:

| box | questions | note |
|---|---:|---|
| new value gone, topic absent | 25 | the notes do not mention what the question is about |
| new value gone, topic mentioned | 6 | the topic survives, the value does not (`b01defab`, `affe2881`, `f9e8c073`, `a1eacc2a`, `0ddfec37`, `89941a94`) |
| notes reset | 6 | notes of 165–511 tokens covering the last few sessions only; every other error has at least 808 |
| asks for the earlier value, which is gone | 3 | `0977f2af`, `e66b632c`, `f685340e`: the newer value is in the notes or the window |
| nearly right | 1 | `07741c45`: "shoe rack" and "closet" are in the notes, "under the bed" is gone; judged `no` |
| old value kept | 0 | |
| wrong reasoning | 0 | |

Nine of the 41 ask for the earlier value or for both. Among them `0977f2af`,
`e66b632c` and `f685340e` had the newer value and answered it: the one place
where "the summary replaces the old value" shows, and it shows as an error.

Of the 41, 37 are "I do not know"; the notes counted 38 and listed three
others, and the rows add `0977f2af`, which answered "Air Fryer".

## `single-session-user`, wrong (47)

| box | questions | note |
|---|---:|---|
| fact gone, topic absent | 28 | 5 of them "adjacent": the conversation survives, the fact does not |
| fact gone, topic mentioned | 6 | |
| notes reset | 11 | 62–733 tokens, judged on content; the other errors go down to 603, so there is no gap as in `knowledge-update` |
| the model's | 2 | `4100d0a0` and `b86304ba`, the fact in the window, "I do not know" |

All 47 are "I do not know" in some form. In M2, 8 of `RetrievalMemory`'s 9
errors with the evidence in the context were the model's "I do not know";
here that box is nearly empty, 2 of 47. `b86304ba` carries the M2 data flag:
the question says "painting of a sunset", the evidence "flea market find".
`4100d0a0` answered "I do not know your ethnicity based on the conversation
history provided" with "my mixed ethnicity - Irish and Italian" in the
window; whether that is the same miss as M2's or a refusal cannot be told
from the row.

## Correct (34)

| the answer was in | single-session-user | knowledge-update |
|---|---:|---:|
| the notes only | 10 | 11 |
| the window only | 3 | 4 |
| both | 1 | 4 |
| neither (a guess) | 0 | 1 |

`50635ada` is the guess: the question asks for the earlier status, the notes
hold only the newer one, and the model inferred "Premier Silver". `51a45a95`
carries its M1 data flag: the marked turn does not say Target, and the model
assembled the answer from "Cartwheel app from Target" in the notes.
`603deb26` is counted as answered from the notes by the reading; the rows
show the turn that restates the fact, `answer_8afdebac_2:10`, in the window
as well, as in M2, so it belongs to "both" by the window's restatement. In
every correct `knowledge-update` answer the notes held the newer value only;
in none both.

## What the rows add

- **The ask-again collapses the notes.** In 78 consolidations in 67 of the
  122 questions, a reply over 1,000 tokens was followed by a reply under 30%
  of its size: the second call of 0015, told the word count, returned a
  fraction of the notes. Fifteen of the seventeen "reset" questions had such
  a collapse; the notes then grow again session by session, so how short the
  final notes are depends on how recently it happened. Five final notes are
  under 300 tokens, 19 under 600, 82 at or over 900. Under 600 tokens 3 of 19
  answers were right; at or over, 31 of 103.
- **Two final notes end mid-sentence**, `58ef2f1c` ("They enjoyed
  volunteering at the ") and `1cea1afa` ("User recently finished reading "),
  both where a quoted title would start. The harness cannot have cut them:
  an unescaped quotation mark makes the whole reply unparseable, which is a
  failed call, not a shorter string. The model closed the JSON string at the
  quotation mark. In `58ef2f1c` the reply held nothing else (957 output
  tokens against 953 in the summary); in `1cea1afa` it held 89 more tokens
  under other keys, which the strategy drops as 0015 says. Both questions
  also have failed calls, which fits attempts that broke the JSON outright.
  This is the model's JSON-mode habit, the same family as the loops of 0016,
  and it loses the end of the notes, the newest part, without counting as a
  cut or a skip. How often it happened in the 5,874 intermediate notes cannot
  be seen: a later rewrite covers the trace, and successful replies are not
  kept raw.
- **The Chinese notes of `36580ce8` are the cut rule.** The last three
  replies held 934, 1,006 and 1,006 tokens; the final notes hold 62. The text
  has no spaces and no line breaks, two Chinese full stops, and three ASCII
  full stops inside "ME2.4" and the like. 0017 cuts at the first sentence
  start after `.`, `!`, `?` or a line break at which the rest fits, and the
  Chinese "。" is none of them, so the cut fell inside "ME2.4" near the end
  and kept 62 tokens. One question; the rule was applied as written.
- **Four final notes are not in English**: Italian in `89941a94`,
  `c14c00dd` and `f4f1d8a4`, Chinese in `36580ce8`. The prompt says "Keep
  the notes in the language of the conversation", and a filler session in
  another language takes the notes with it.
- **Distance decides.** Correct answers by the tokens between the newest
  evidence and the question: 12 of 17 under 8,000; 13 of 26 from 8,000 to
  20,000; 9 of 29 from 20,000 to 40,000; 0 of 28 from 40,000 to 70,000; 0 of
  22 beyond. Nothing stated more than about twenty sessions before the
  question survived into the notes.
- The evidence was in the window in 16 questions, 12 of them right.

## Against the hypotheses

**The third hypothesis does not hold as stated.** `ConsolidatingMemory`
answers 20 of 61 changed-fact questions against `RetrievalMemory`'s 47. The
mechanism the hypothesis names is real: in every correct `knowledge-update`
answer the notes held the newer value only, and in none both, so the summary
does replace. What the hypothesis did not say is how little survives the
replacing: in 42 of the 61 questions the notes held neither value, and the
"old value kept" box is empty because the old value was gone too. Where the
question asks for the earlier value, replacing is the error (`0977f2af`,
`e66b632c`, `f685340e`).

**"Loses detail and pays for extra calls" holds with room to spare.** 14 of
61 old facts against 50; the value absent from the notes in 82 of 88 errors;
four times the cost. The loss is not in the reading: the consolidator read
every evidence turn. It is in the rewriting, and the rewriting is bounded
by distance: nothing from more than about twenty sessions back survived.

**The row still beats the baseline**, 14 and 20 against 3 and 9, and the
notes alone account for 21 of its 34 correct answers.

## Limitations carried to the report

- The notes are written by a weaker model than the one that answers (0010),
  and that model did not keep to its size: the size was held by a second call
  in 2,759 of 5,874 consolidations and by a cut in 2,161 (0015, 0017). The
  second call sometimes returns a fraction of the notes: 78 collapses in 67
  questions.
- The model sometimes closes the JSON string at a quotation mark and the end
  of the notes is lost without being counted; two final notes show it, the
  intermediate rate is unknown. A future record should keep every reply raw
  and treat a string that ends without punctuation as a failed attempt.
- The cut rule's sentence ends are Latin punctuation; one Chinese set of
  notes collapsed to 62 tokens for it. A future record should add `。`, `！`
  and `？`.
- Four final notes are not in English, following a filler session's
  language.
- The model loops on some inputs; 17 sessions skipped, none with evidence.
- The judge's line between an inference accepted and one rejected is its
  own, and three answers sit on it.
- The commit stamp is `fa2d293+dirty` from untracked result files.

## Data notes carried from M1 and M2

`51a45a95` (the marked turn does not name Target), `b86304ba` (question and
evidence name the object differently), `a2f3aa27` ("close to 1300" against
1300), `69fee5aa` (the new value is 37 + 1, never written), `89941a94`
(gravel against hybrid). All five behaved as flagged. `b01defab` and
`603deb26` again had turns of the evidence session restating the fact in
the window.
