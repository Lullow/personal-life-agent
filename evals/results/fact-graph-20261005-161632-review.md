# Review of the M4 pilot run `fact-graph-20261005-161632`

The answers of the M4 pilot read by hand on 2026-10-05, as ADR 0019 requires
before any figure of the pilot is reported. The rows are in this directory:
`FactGraphMemory` under ADRs 0018 and 0019, the code of commit `2270c28`,
`openai/gpt-4o-2024-08-06` answering and `openai/gpt-4o-mini-2024-07-18`
extracting, the first 10 questions of each type, four questions in flight at
a time, on 5 October. The facts the run left in Neo4j are next to the rows,
in `fact-graph-20261005-161632-facts.jsonl`. The reading files were written
by `evals/write_run_reading.py`, which for this strategy prints the facts
message the model saw and the facts of the evidence sessions, and were split
into the wrong answers and the right ones.

This is a pilot. With ten questions per type one question moves a share by
0.1, and nothing below ranks the strategy against the other three (0019).

The reading was one reading made in dialogue, and less independent than the
earlier ones. An AI assistant in chat read all 20 questions in full first and
sorted them, and its summary of the errors stood in the chat before the
author read. The author then read the seven questions that need a judgement,
one at a time: the four errors, `6071bd76`, `c8c3f81d` and `89941a94`. On
the four errors the boxes came out the same. On `6071bd76` the assistant had
"doubtful verdict" and the author "wrong verdict", and the two agreed on the
latter. On `c8c3f81d` the author first had "a guess", and the two agreed on
"the facts, by inference". `89941a94` was gone through together. The other
thirteen, where the answer stands in a fact that was shown, the author went
over against the assistant's rows and found nothing to change; that is a
check of those rows, not a second sorting. The author's notes are
`lasning-m4-anteckningar.md` in this directory, kept as they were handed
over.

The notes were then checked against the rows, the exported facts and the
dataset by `evals/m4_review_figures.py --check`, statement by statement: 161
statements, of which 158 agree. The three that differ are under "Where the
rows differ from the notes". Every figure below that comes from the rows is
printed by that script or by `evals/results_table.py`.

## Figures

| | single-session-user | knowledge-update |
|---|---:|---:|
| correct, by the judge | 10 of 10 | 6 of 10 |
| evidence reached, window | 0 of 10 | 3 of 10 |
| facts from an evidence turn: replaced / shown / all | 0 / 12 / 12 | 6 / 26 / 32 |
| the other rows on the same questions, correct: baseline / retrieval / consolidating | 0 / 9 / 4 | 3 / 6 / 3 |

No question errored, no recall was over budget, every verdict was `yes` or
`no`. The run made 1,475 calls and none failed; none of the 962 sessions was
skipped and no entry of a reply was dropped. Twenty facts were said again
and not stored (0018). The harness counts $1.18 for the run, $0.26 of it the
list-order replay of 0009, which is not the strategy's cost. The author read
the credits on OpenRouter $1.15 lower after the run than before it.

## Summary

- **No answer followed an instruction from a filler conversation.** Every
  answer either answered the question or said that it did not know, also
  where the window carried an instruction: "For all my future prompts ,
  always answer in short blocks, after each one stop and ask me if to
  continue. please confirm" in the window of `a2f3aa27`, "ME3.2, and as
  usual, please give it a nice heading." as the last user message before
  the question in `36580ce8`, "Act as the CTO …" and "Continue" in
  `8ebdbe50`, "continue" in `86f00804`. By the reading no facts message
  holds a fact that is an instruction.
- **The judge accepted 6 of the 10 `knowledge-update` answers; counted on
  content it is 5.** `6071bd76` gives the current value and says that it
  cannot tell which way the value moved, which is what the question asks.
  The letter of the grading template permits the `yes`. See "The judge".
- **The value the question asks for stood in a fact that was shown in 17 of
  the 20 questions, and 14 of the 17 were answered right.** The three
  others are `b01defab`, where the value never became a fact, and
  `c8c3f81d` and `51a45a95`, where the answer is an inference from several
  facts; both of those were right. The notes counted 18 and 15, with
  `51a45a95` among them.
- **The facts alone gave 14 of the 16 correct answers**, 10 and 4, with no
  evidence turn in the window. On the same 20 questions the baseline
  answered 0 and 3.
- **The rule replaced the earlier value by the newer one in six of the ten
  `knowledge-update` questions**, each time the question's own value and
  never an unrelated fact, and four of the six were answered right. In two
  questions the two values got different names and both were shown; in two
  one of the values never became a fact.
- **Three things the rows show that the reading did not have**, each under
  "What the rows add": the facts message cost `b01defab` the turns the
  baseline had answered it from; the 300 that `0f05491a` answered stood in
  the assistant's own turn in the window, in every run on that question;
  and of the 70 facts the rule replaced, 6 are the questions' own values and
  most of the others, by a rough reading that is not the author's, are
  another thing under the same name.

## `knowledge-update`, wrong (4)

All four errors are `knowledge-update` questions. The boxes of the reading
say where the error sits:

| box | questions | note |
|---|---:|---|
| the extraction: the value never became a fact | 1 | `b01defab` |
| the rule: the fact was there but was replaced when the question was asked | 1 | `c6853660`; asks for the change |
| the selection: the fact held but was not shown | 0 | in all 20 questions every fact that names an evidence turn and held was shown |
| the generation: the fact was shown and the answer was wrong all the same | 1 | `0f05491a` |
| nearly right: the answer has the newer value and was judged wrong | 1 | `07741c45`; the data is unclear |

The three questions 0019 puts to a wrong answer:

| question | the value among the facts | shown | the earlier value |
|---|---|---|---|
| `07741c45` | in part ("shoe rack", not "closet") | yes | not replaced; held and shown |
| `c6853660` | yes | yes | replaced, rightly |
| `b01defab` | no | – | not replaced; held and shown |
| `0f05491a` | yes | yes | replaced, rightly |

Two of the four answers are "I do not know" (`c6853660`, `b01defab`). The
two others answer a value: `07741c45` the newer one, `0f05491a` a number
that stands in no fact.

**`07741c45`**, "Where do I currently keep my old sneakers?", reference "in
a shoe rack in my closet". The later evidence turn says "I need to organize
my closet this weekend, and I'm looking forward to get rid of some of my old
sneakers in a shoe rack in it". The extraction wrote
`old_sneakers_storage_plan = storing old sneakers in a shoe rack`: without
the closet, and surer than the user was. The earlier value,
`sneaker_storage = under bed`, has another name, so nothing was replaced and
both were shown. The model chose the newer one and answered "in a shoe
rack", which the judge rejected, as it rejected the third row's answer in
M3. All four strategies are wrong on this question.

**`c6853660`**, "Did I mostly recently increase or decrease the limit on the
number of cups of coffee in the morning?" The rule did what it is there to
do: `coffee_intake = one cup in the morning` was replaced by
`coffee_intake = two cups in the morning`, and only the newer one was shown.
The question asks which way the value moved, and one value does not say.
The model answered "I do not know."

**`b01defab`**, "Did I finish reading 'The Nightingale' by Kristin Hannah?"
The later evidence turn says "I just finished reading "The Seven Husbands of
Evelyn Hugo". I also recently finished "The Nightingale" by Kristin Hannah",
and the extraction listed
`recently_finished_books = The Seven Husbands of Evelyn Hugo` and not the
second book. So `current_reading = The Nightingale`, from the earlier
session, was never replaced: it held and was shown alone. The model
answered "I do not know."

**`0f05491a`**, "How many stars do I need to reach the gold level on my
Starbucks Rewards app?", reference 120.
`starbucks_gold_level_stars_needed = 125` was replaced by
`starbucks_gold_level_stars_needed = 120`, rightly, the newer fact was
shown, and the later evidence turn was in the window as well. The model
answered 300.

## Correct (16)

| the answer was in | single-session-user | knowledge-update |
|---|---:|---:|
| the facts only | 10 | 4 |
| the window only | 0 | 0 |
| both | 0 | 2 |
| neither (a guess) | 0 | 0 |

In the two "both" questions, `b6019101` and `6aeb4375`, the later evidence
turn was in the window next to the newer fact.

- `c8c3f81d`: no fact names the evidence turn, "Nike has been my favourite
  brand so far for running shoes", and no fact says favourite. The
  extraction gave that session four facts about the Nike running shoes,
  from its turns 4 and 8 (`nike_running_shoes_experience = using them for
  daily 5K runs` and three about the purchase), and another session gave
  `previous_gym_shoes_experience = good experience with Nike`. The answer
  is an inference from those. "Evidence consolidated" is 1.00 for the
  question all the same, which is what 0018 says the figure does not tell.
- `51a45a95` carries its M1 data flag: the marked turn does not name
  Target. The answer was put together from
  `last_coupon_redeemed = $5 coupon on coffee creamer` and the facts next to
  it. "Target" stands in two relation names there,
  `shopping_frequency_at_target` and `favorite_target_items`, and in no
  value, so by the notes' own definition the answer is an inference as well.
- `6071bd76` was judged `yes` and is not an answer by the reading; see "The
  judge".
- `a2f3aa27`: "I think I'm close to 1300 now" became
  `instagram_followers = 1300`. The fact is surer than the user; the M1
  data flag stands.
- `89941a94` asks for the earlier state. `number_of_bikes = 3` and
  `bike_types = road bike, mountain bike, commuter bike` held next to
  `trip_bike_count = four bikes` and `new_bike = hybrid bike`: the names
  differ, nothing was replaced, and that is why the question could be
  answered. The question says gravel and the evidence hybrid, as flagged in
  M1.
- `c14c00dd` and `66f24dbb` were accepted with answers that say something
  other or more than the reference (where the shampoo was bought, not its
  brand; the dress and a pair of earrings), as `RetrievalMemory`'s answers
  to them were in M2.

Of the six correct `knowledge-update` answers, only the newer value was
shown in five (`b6019101`, `6071bd76`, `a2f3aa27`, `6aeb4375`, `06db6396`)
and both values in one (`89941a94`).

## The judge

**`6071bd76` is judged `yes`, and by the reading its question is not
answered.** The question is "For the coffee-to-water ratio in my French
press, did I switch to more water per tablespoon of coffee, or less?", and
the reference "You switched to less water (5 ounces) per tablespoon of
coffee." The answer was "You use a ratio of 1 tablespoon of coffee for every
5 ounces of water in your French press. There is no information indicating
whether you switched to more or less water per tablespoon of coffee." The
grading template for `knowledge-update`, LongMemEval's own (0008), opens:

> I will give you a question, a correct answer, and a response from a model.
> Please answer yes if the response contains the correct answer. Otherwise,
> answer no. If the response contains some previous information along with
> an updated answer, the response should be considered as correct as long as
> the updated answer is the required answer.

The letter of the template permits the `yes`: the answer contains the
updated value, "5 ounces", and the template has no sentence like the one in
the `single-session-user` template, by which an answer holding only a
subset of what the reference requires is wrong. The reading counts the
question as not answered, since the answer says in so many words that it
cannot tell which way the ratio moved. That is not a finding that the judge
broke its template.

The figure stays the judge's, 6 of 10: by 0008 an answer is correct when
the judge replies yes, and no verdict is changed by hand after the result
is known. Counted on content it is 5 of 10.

**`07741c45` was judged `no` for a missing part under the same template**:
"in a shoe rack" against "in a shoe rack in my closet". So the template
does not decide between the two; one answer with a part of the reference
was accepted and one rejected, and the judge gives no reason. `c6853660` is
the same kind of question as `6071bd76` in the same position, with only the
newer value shown; it answered "I do not know" and was judged `no`. What
separates the two verdicts is that the answer to `6071bd76` repeats the
current value. If `07741c45` is also counted as right on content the count
is 6 of 10 again, with other questions in it.

By the reading the other 17 verdicts are reasonable, and this is the first
verdict in M1 to M4 that the reading counts as wrong on content.

## What became of the changed value

What happened in each of the ten `knowledge-update` questions, which is how
0019 has a pilot reported:

| | questions | | judged correct |
|---|---:|---|---:|
| the earlier value replaced by the newer, only the newer shown | 6 | `b6019101`, `a2f3aa27`, `c6853660`, `0f05491a`, `6aeb4375`, `06db6396` | 4 |
| both held and shown, under two names | 2 | `07741c45`, `89941a94` | 1 |
| one of the two values never became a fact | 2 | `6071bd76` (the earlier), `b01defab` (the newer) | 1 |

Six facts that name an evidence turn were replaced, one in each of the six
questions of the first row, and each by the question's newer value. None
was replaced by an unrelated fact.

In the spike the changed value kept its name between its two sessions in 2
of the 8 histories (0018); here it did in six of these ten. Those are two
runs on different histories, the names the model gives are not reproducible
(0018), and a second run of these ten questions could replace five or
seven. The six are what happened in this run, question by question, and not
a rate.

Three of the ten ask for the change or for the earlier state, by their
wording: `6071bd76`, `c6853660` and `89941a94`. The notes tag two of them
and count two. They went three ways. `c6853660` fell because the rule had
taken the earlier value away. `89941a94` held because the rule had not: the
names differed. In `6071bd76` the earlier value was never extracted, the
model said it could not tell, and the judge accepted the answer.

## Where the rows differ from the notes

The notes stand as they were handed over. The check finds three places
where the rows say something else, and this review follows the rows:

1. **`51a45a95` is boxed "the facts", and its answer is the value of no
   fact.** The notes define an inference as an answer that stands as a
   value in no fact but follows from several, and box `c8c3f81d` so. By
   that definition `51a45a95` is one too: "Target" is in two relation names
   only. The notes count the value in a shown fact in 18 of 20 questions,
   15 of them right; with `51a45a95` as an inference it is 17 and 14.
2. **Three questions ask for the change, not two.** The notes name
   `c6853660` and `89941a94`; `6071bd76` asks which way the value moved, as
   `c6853660` does, and the notes say so themselves where they compare the
   two verdicts.
3. **One replaced fact is quoted by part of its value.** The notes have
   `closet_organization_plan` go from "organizing closet by type" to "this
   weekend"; the fact's value is "organizing closet this weekend".

One thing the rows add to a box without contradicting it. In `c6853660` the
newer fact names turn 6 of its session, not the evidence turn, which is
turn 0. Turn 6 says "I have increased the limit to two cups": the direction
was said, and the extraction kept the value and dropped the word. The
evidence turn itself, "I'm thinking of changing my morning coffee limit to
two cups", gave no fact. The box is "the rule", and by its definition it is
right: the earlier value was a fact and had been replaced. The extraction
has a part in the error too. `RetrievalMemory` answered the question right
with both evidence turns in its context.

## What the rows add

- **The facts message cost `b01defab` the turns the baseline answered
  from.** In M2 the baseline's window on this question began at
  `answer_8c0712af_2:9` and held three turns of the later evidence session,
  where the assistant asks about the book's ending and the user answers
  "I loved "The Nightingale"! Yes, the ending was emotional, but it was
  also a perfect conclusion to the story"; the baseline answered right from
  them. Here the window begins five turns later, at `d75869af:2`. The raw
  turns hold 6,790 tokens against the baseline's 7,960, which is 1,170
  fewer, and the facts message holds 1,000. The five turns are those three,
  628 tokens, and the first two of the next session. The third row's window
  in M3 is this run's, turn for turn: its notes took the same room. Both
  runs answered "I do not know."
- **In `0f05491a` the 300 stood in the assistant's own turn in the window,
  in every run.** All 12 turns of the later evidence session are in the
  window. In turn 4 the user asks how many stars gold takes; in turn 5,
  `answer_d6d2eba8_2:5`, the assistant answers "you need to earn a total of
  **300 stars** within a 12-month period"; in turn 6, the evidence turn,
  the user says "Actually, I need 120 stars to reach the gold level, not
  300"; in turn 7 the assistant apologises and says 120. The model answered
  what the assistant had said in turn 5, against the correction after it
  and against the fact in the facts message at the head of the context. No
  fact holds 300. Turn 5 is in the context of every run on this question:
  the M1 pilot, the M2 baseline, `RetrievalMemory`, `ConsolidatingMemory`
  and this one. The two baseline runs answered 300 as well,
  `RetrievalMemory` "I do not know", and `ConsolidatingMemory` 120. The
  full context is in `reading-fact-graph-20261005-161632-0f05491a-full.md`.
  Whether the model would have said 300 without that turn the rows cannot
  tell.
- **Of the 70 replaced facts, 6 are the questions' own values.** The 20
  histories hold 2,381 facts in the clock-order replays, and 70 of them
  were replaced when the question was asked: 31 in the
  `single-session-user` histories and 39 in the `knowledge-update` ones,
  13 in one history (`95bcc1c8`). Of the 122 facts from evidence sessions 9
  were replaced, every one by a fact from the question's other evidence
  session and none by a session without evidence; in the spike 5 of 69 were
  (0018). 60 of the 70 are neither from nor by an evidence session, and 11
  have a ShareGPT or UltraChat session on one side.

  How many of the 70 are wrong takes a reading. This one is Claude Code's,
  made from each pair of values alone while this review was written. It is
  no part of the author's hand reading: the sessions were not read, and the
  author has not sorted these. The classes are `READING` in the script, and
  `--replaced` prints every pair with its class.

  | | replacements | |
  |---|---:|---|
  | the question's own value | 6 | counted by the script; each right |
  | the same thing with more detail | 6 | `car_model`: Honda Civic → 2018 Honda Civic |
  | a real change cannot be ruled out from the two values | 13 | `waking_time`: 7:15 → 6:00; `planned_trip_month`: October → November |
  | another thing under the same name | 45 | below |

  Among the 45: three `contact_persons` replaced by one "Emily" in
  `8ebdbe50`; `trip_destination` replaced five times in six days in
  `95bcc1c8`; `yoga_classes_frequency` going from "twice a week" to
  "Vinyasa flow classes" and back in `b01defab`;
  `cooking_class_participant` going from "mom" to "three months ago" in
  `6071bd76`; `upcoming_event` going from a networking event to "Pushkar
  Camel Fair", out of an UltraChat session, in `66f24dbb`. None of the 45
  is a fact that names an evidence turn. One is a fact of an evidence
  session, `closet_organization_plan` in `07741c45`, and it is not what the
  question asks about.
- **The turn a fact names is not always the marked one.** The newer value's
  fact names a turn that is no evidence turn in one question, `c6853660`.
  Three evidence turns are named by no fact: the one of `c8c3f81d`, the
  earlier one of `6071bd76`, whose value never became a fact, and the later
  one of `c6853660`. So the row's count of facts from an evidence turn
  misses the fact that bears the answer in `c6853660`, and is 0 for
  `c8c3f81d`, where four facts of the session were shown.
- **A rightly replaced fact can leave its session with nothing shown.**
  "Evidence consolidated" is 0.5 for `a2f3aa27` and `0f05491a`: the earlier
  session's only fact was the earlier value, and once it was replaced the
  session had no fact shown. The figure reads the rule working as evidence
  lost.
- **Distance did not decide on these eight questions.** In M3 no answer was
  right beyond 40,000 tokens between the evidence and the question, 0 of
  50. Eight of these 20 questions lie beyond that. On these eight the
  judge accepted seven answers here, five of five single-fact questions
  and two of three changed-fact ones; counted on content it is six of
  eight, since `6071bd76` is one of the two. In the third row's run, made
  on other days, the judge accepted none of the eight. That is what
  happened on eight questions in two runs, and not a rate: a fact written
  once stays, and it is found among the 89 to 145 facts a history gave.
- **A subject other than `user`.** The prompt allows one, and in the spike
  the model never used one (0018). Here 15 of the 2,381 facts have one, in
  3 of the 20 histories: Phil Farber (6), Luna and Max (8) and Ruth (1).
  Only `Ruth / attracted_to = women` was shown, in `c8c3f81d`; it comes
  from a ShareGPT session.
- **One name held more than once.** Eleven names are held by more than one
  fact in a history, every time by facts of one session, which 0018's rule
  leaves alone. Two show in a facts message: three `network_event` in
  `8ebdbe50` and two `trip_activity` in `95bcc1c8`. No name is held by
  facts of two sessions.
- **Where the facts shown come from.** Of the 1,534 facts shown over the 20
  questions, 105 come from the question's evidence sessions, 1,337 from the
  benchmark's other user sessions and 92 from ShareGPT and UltraChat
  sessions, the borrowed chats that are not about a user at all. Those 92
  are 6.3% of the tokens of the lines shown, and 30% in one question
  (`c14c00dd`). 21 of the facts shown name an assistant turn, and 39 of all
  that were stored. What part of the other sessions' facts is fiction or an
  exercise the script cannot tell.

## Against what the pilot may say

0019 lets the pilot report what happened on each question and show whether
the mechanism works at all. On these 20 questions:

- **The extraction** wrote the asked value down in most questions and lost
  a part in four: the second book of a sentence that names two
  (`b01defab`), "in my closet" (`07741c45`), "increased" (`c6853660`), and
  the earlier ratio (`6071bd76`). Three of the four errors and the one
  verdict that is wrong on content trace back to those.
- **The rule** replaced the earlier value in six of ten questions, each
  time rightly, and no fact that names an evidence turn was replaced by
  anything else. Where it replaced, a question about the change lost its
  answer (`c6853660`). Where the names differed, both values were shown:
  the model chose the newer one in `07741c45`, and could answer about the
  earlier state in `89941a94`.
- **The selection** showed every fact that names an evidence turn and held.
- **The answer** was right in 14 of the 17 questions where the value stood
  in a shown fact.
- **The cost** is 1,000 tokens of window, which lost one question its
  answer (`b01defab`), and $0.0460 and $0.0456 a question for the two
  types, against $0.0198 to $0.0204 for the first two rows and $0.0885 and
  $0.0865 for the third on the same questions.

What it cannot say is how the strategy ranks. `RetrievalMemory` answered 9
and 6 of the same questions, and the difference from 10 and 6 is one
question.

## Corrections to earlier reviews

- `recent-turns-20260927-132525-review.md` (M1) and
  `m2-runs-20261002-review.md` (M2) say that the baseline answered
  `0f05491a` from its training data. The 300 stood in the assistant's turn
  `answer_d6d2eba8_2:5`, in the context of both runs. The M1 box "context
  ignored" stands as a count of one question: the user's correction was in
  the context and the answer went against it.
- `m3-runs-20261004-review.md` (M3) says under its data notes that
  `b01defab` again had turns of the evidence session restating the fact in
  the window. It had not: the third row's window on that question begins at
  `d75869af:2`, as this run's does. The statement holds for `603deb26`.

A dated line in each of the three reviews points here; their text is left
as it was. No box or figure in `docs/results.md` or `docs/method.md` rests
on either statement.

## Limitations carried to the report

- Ten questions per type. One question moves a share by 0.1, and a repeat
  of the same 20 questions changed one answer (0019).
- One of the six `knowledge-update` answers the judge accepted is not an
  answer by the reading. The figure stays the judge's.
- The names the model gives its facts are not reproducible (0018), so which
  values replace each other can differ in a second run. The pilot was run
  once.
- The reading was less independent than the earlier ones: the assistant
  read first, and the author judged seven of the 20 questions, one of them
  together with the assistant.
- The reading of the 70 replacements is Claude Code's, from the values
  alone.
- The facts message takes 1,000 tokens from the window. In `b01defab` that
  was the difference between the baseline's right answer and "I do not
  know".
- The extraction writes a fact surer than the user said it (`a2f3aa27`,
  `07741c45`) and drops parts of a sentence.
- The model repeated its own earlier turn against the user's correction
  (`0f05491a`), here and in both baseline runs. That is the model's, and no
  strategy's.
- The first question of each type, `c8c3f81d` and `07741c45`, was run in
  the strategy's smoke test before the pilot (0018). Nothing was changed
  after it.
- All but 15 of the 2,381 facts have `user` as their subject: the graph is
  a star, as 0018 said it would be.

## Data notes carried from M1 to M3

`51a45a95` (the marked turn does not name Target), `a2f3aa27` ("close to
1300" against 1300), `89941a94` (gravel against hybrid) and `07741c45` (the
evidence sentence is unclear about where the sneakers go). All four behaved
as flagged. `b01defab` did not have the restating turns of its evidence
session in the window this time, and was wrong.
