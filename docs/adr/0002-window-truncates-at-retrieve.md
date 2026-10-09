# 0002 — The window truncates at retrieve, not at write

Status: accepted
Date: 2026-09-06

## Context

The buffer this layer replaces lived in `ConversationAgent._append`. It
appended a message and then discarded the oldest whenever the list grew past
`max_history_turns * 2`. The dropped message was gone: nothing afterwards
could ask what had been thrown away.

`RecentTurnsMemory` is the baseline the other two strategies are measured
against, and the measurement is retrieval recall — of the records that should
have reached the model's context, how many did. A strategy that has destroyed
the records it failed to surface cannot answer that question about itself. The
denominator is missing.

## Decision

`RecentTurnsMemory` keeps every record it is written and applies its window
inside `retrieve()`, filtering by the `at` cutoff first and then taking the
most recent messages that fit the token budget. `write()` only appends.

The records that fall outside the window remain in the store and are reachable
through the `records` property.

## Consequences

Recall is measurable for the baseline on the same terms as for the other two
strategies. All three keep everything and differ only in what they choose to
surface, which is the axis the comparison is actually about.

The messages the model sees are unchanged. This was verified when the memory
Protocol was wired in: all 254 tests that existed beforehand passed without
edits, including the ones asserting the exact contents of the window.

**The baseline now models what a sliding window would have found, not what the
previous implementation still held in memory.** Those coincide for everything
the model sees, and they diverge for everything else — recall, and any
question of the form "what did the strategy miss". This distinction belongs in
the method section of the write-up. Reporting the baseline's recall without
stating it would describe a system that was never run: the old code could not
have produced that number at all, because it had already deleted the evidence.

Memory grows without bound within a session. For a household assistant holding
a conversation this does not matter; for the evaluation, which replays long
multi-session histories, the whole history is held in memory by design, since
that is what the other strategies do too.

A future persistent store inherits this: it writes every record and narrows on
read. Compaction is a strategy's decision, expressed as consolidation, never a
side effect of writing.
