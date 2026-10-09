# Architecture Decision Records

One file per decision that shapes the code, numbered in the order it was
taken. Each record answers three questions and nothing else:

- **Context** — what was true that forced a choice. The constraints, not the
  solution.
- **Decision** — what was chosen, stated in the present tense.
- **Consequences** — what follows, including what got worse. A record that
  lists only benefits is not finished.

## An ADR is never edited

Not to fix a decision that turned out badly, and not to keep it current. The
record says what was known and chosen at the time, and that is the whole value
of it — a decision that reads as obviously wrong today is evidence about what
was not obvious then.

When a decision is revisited, write a **new** record that supersedes the old
one. Mark the new one `Supersedes: NNNN` and add `Superseded by: NNNN` as the
only change ever made to the old file. The reasoning that was replaced stays
readable.

Typos and broken links may be fixed. Reasoning may not.

## Writing one

Copy the shape of an existing record. Filenames are
`NNNN-short-slug-in-english.md`, numbered from the highest that exists.

Write one when a decision constrains code that will be written later, when a
reasonable person would pick differently, or when the reason lives in a
constraint the code cannot show — a benchmark's requirement, a dependency
that was rejected, a measurement that has to stay comparable. Not for
decisions the code already states plainly.
