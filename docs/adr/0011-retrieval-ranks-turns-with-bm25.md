# 0011 — RetrievalMemory ranks turns with BM25 and shows them in the order they were said

Status: accepted
Date: 2026-10-02

## Context

M2 builds `RetrievalMemory`: recall by relevance to the question, over
everything written, with no way to overwrite a stale fact. Three earlier
records leave decisions to this one:

- `docs/vg-project.md` requires the order of its `messages` to be decided and
  recorded before it is measured.
- 0008 shows the model the recalled messages as chat turns with no dates, so on
  a `knowledge-update` question order is the only thing that tells the model
  which value is newer. The order has to be settled within that record: dates
  for one strategy and not another would make the comparison about the dates.
- 0010 assumed an embedding index for its estimate, named BM25 as the other
  index M2 may choose, and requires this record to say how embedding calls are
  counted, since 0006 covers chat calls only.

What is already fixed constrains the rest. Every strategy gets the same
8000-token budget, counted over the content of what it returns (0006, 0007).
Recall and precision are per turn (0009), and `Retrieval.messages` is documented
as oldest first. The harness passes the question's text as `query`, without the
date line. `retrieve(at=T)` must not surface anything stamped later than `T`.

In the 122 histories that 0010 measures, assistant turns hold 87% of the
tokens, and 183 of the 185 evidence turns are user turns. Three records are
larger than the budget. None of them is evidence: the largest evidence turn is
533 tokens.

Nothing under `life_agent/` depends on a numeric library or a network call
besides the chat client, and the tests run offline.

The plan leaves no slack. M2 was due on the day this record is written, and
M3's hard stop is 6 October.

LongMemEval's own retrieval (`src/retrieval/run_retrieval.py` at commit
`d0c699faf593726d96a6c75768e0fd2016d1feb8`) offers BM25 next to three dense
retrievers (`flat-bm25`, line 35). At turn granularity it indexes user turns
only (lines 213–215).

## Decision

**The unit is one record.** Every record written is indexed on its own
content, user and assistant turns alike. A turn is not joined with the turn
before or after it.

**Records are ranked with BM25**, a score built from the words a record shares
with the query, where a rare word counts for more than a common one and a long
record is not favoured for its length.

- A text's terms are its maximal runs of letters and digits, after
  `str.casefold()`. No stemming and no stopword list.
- For a query `q` and a record `d`, summing over the distinct terms of `q`:

  ```
  score(q, d) = Σ idf(t) · tf(t, d) · (k1 + 1) / (tf(t, d) + k1 · (1 − b + b · |d| / avgdl))
  idf(t)      = ln(1 + (N − n(t) + 0.5) / (n(t) + 0.5))
  ```

  with `k1 = 1.2` and `b = 0.75`, the defaults of Lucene. `tf(t, d)` is how
  often `t` occurs in `d`, `|d|` the number of terms in `d`.
- `N`, `n(t)` and `avgdl` are computed at `retrieve()` over the records with
  `at <= T` and no others, so a later record cannot move the ranking either.
- Equal scores are ordered with the record written later first.

**Recall fills the budget in rank order.** Walking down the ranking, a record
is taken if it fits in what is left of the budget and passed over if it does
not, and the walk goes on to the end. A record that shares no term with the
query is never taken. The budget is never exceeded.

**The messages are returned in the order they were written**, oldest first,
which in a replay is the order of 0004. Roles and content are unchanged. No
rank, score, date or separator is shown. `sources` follows the same order.

**The strategy makes no model call.** Its cost for a question is the answer
call. There are no embedding calls to count, and 0006 stands as it is.

**User-turn recall, as a secondary figure for this strategy.** Recall, and
whether any evidence reached the context, are also computed with only the user
turns written to the strategy and nothing else changed, which is how
LongMemEval indexes turns. `E` stays as the dataset marks it, so an evidence
turn spoken by the assistant counts as missed. No answer is produced from that
recall. The figures are reported next to the primary ones. They are declared
here, before either index has been measured, so that the index cannot be
chosen afterwards.

The harness registers it as `retrieval`, built with the harness's token
counter and nothing else.

These parameters are fixed here. A dry run computes recall and precision for
every question without a model call, so they could be tuned for free; they
are not changed after the first dry run of this strategy.

Considered and rejected:

- **An embedding index**, `text-embedding-3-small`, as 0010 assumed. It
  matches a paraphrase where BM25 needs a shared word, and it is what
  retrieval memory usually means. It needs three more rules, each with its
  own check: how to embed a message longer than the model's input limit, how
  embedding tokens are counted, and what a cache may hide from the cost. The
  dry run could no longer compute recall offline, and the figures would rest
  on a provider's model. With M2 already at its date, that is the work that
  would cost M3.
- **Rank order, the best match first.** It discards the only signal of which
  value is newer, so the second hypothesis in `docs/vg-project.md` would hold
  by construction rather than by measurement.
- **A fixed k.** It would hand this strategy fewer tokens than the baseline,
  the confound 0007 removed.
- **Stopping at the first record that does not fit.** One long message high in
  the ranking would end the recall with most of the budget unspent.
- **Joining a turn with its reply**, or indexing user turns only as
  LongMemEval does. Both narrow the index toward where this benchmark marks
  its evidence, and a memory of user turns only cannot recall what the
  assistant said. The strategy is defined as recall over everything; what the
  narrower index would have recalled is the secondary figure above.
- **A stopword list or stemming.** Both are bound to one language, and the
  agent's is Swedish. `idf` already gives a common word little weight.

## Consequences

Between the baseline and this strategy only the selection differs: the same
budget, the same order, the same prompt.

When both values of a changed fact are recalled, the newer one comes later, as
it does for the baseline. If the model still answers with the old one, that is
the finding, and 0009's breakdown shows it as `both` against correct.

What the model reads is an excerpt presented as a conversation. Turns are
missing between the ones shown, roles do not alternate, and a question can
appear without its answer. The prompt (0008) does not say so. A marked turn
can also be recalled without the answer being in the context, when the answer
needs a neighbouring turn; the pilot review notes `51a45a95` as such a case.

Assistant turns hold most of the tokens and almost none of the evidence, so a
long answer that matches the question takes budget from the short turn that
states the fact. The user-turn recall shows how much evidence that costs. It
does not show what it costs in correct answers, since no answer is produced
from it.

The matching is lexical. A question that words a fact differently from the
turn that states it can miss it, where an embedding index might not. Without
stemming that includes an inflection: "graduate" does not match "graduated". The row
is reported as BM25 retrieval, not as retrieval in general, and its recall is
not comparable with LongMemEval's, which indexes user turns only.

The harness counts the same cost for this strategy as for the baseline: one
answer call on a full budget. The bill is higher. Every message adds 4 input
tokens that the count leaves out (0010), and a strategy that recalls short
turns sends more messages in a call than the baseline does. 0006 expected that
error to be the same for every strategy; it is not. The number of messages is
the length of `sources` in each row, and the report gives the cost with the
framing added. The $0.25 that 0010 set aside for embeddings is not spent, and
N does not move.

The ranking does not depend on the order records were written in, apart from
ties. 0009's list-order recall is therefore expected to equal the primary
figure for this strategy, and a difference beyond ties would point to a bug.

The statistics are recomputed from every visible record at each `retrieve()`.
That is cheap for one question over one history; an agent recalling on every
turn of a long history would need an index kept up to date instead.

A `kind="outcome"` record is kept verbatim and ranked like any other, so it is
recalled only when it shares words with the query.
