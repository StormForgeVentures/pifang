# Completed ledger — the compacted record of finished work

> One row per finished ticket. Written at wave-boundary compaction when `5-completed/`
> is swept: the ticket's folder leaves the tree and this row replaces it. The **closing
> SHA** is the pointer back into git history, which is the real archive.
>
> This file lives at `handoff/completed-ledger.md` and is authoritative for each type's `max+1`
> numbering alongside `docs/tasks/{1-backlog,2-ready,3-in-progress,4-review,5-completed}/`.
> Scan the full typed ID column here plus that type in every lane before assigning a new `NNN`.
> Numbers are never reused.
>
> **Chunking.** When this file outgrows comfortable reading, split by ticket-number range
> (`handoff/completed-ledger/001-200.md`, `201-400.md`, …) — range boundaries are
> mechanical, and `max+1` only ever needs the newest chunk. Do not split by date or epic.
>
> The optional **Submitter** column is a structured provenance field. Older six-column rows are
> valid and mean no submitter was recorded; readers must use only the first ID cell for identity.
> Resolution prose is not parsed as ticket identity.
>
> **Identity parser rule.** In the live section, only pipe-delimited rows whose first/source-ID cell
> is an exact typed ID (`prd-NNN`, `issue-NNN`, `chore-NNN`, or `spike-NNN`) reserve identity.
> Headers, separators, rows with a blank or non-ID first cell, non-table lines, and everything after
> `## Legacy` are ignored for
> identity; they are not whole-line scanned. The remaining cells are opaque, so both six- and
> seven-column rows work and malformed/non-ID rows never allocate from prose.

## Live tickets

Tickets that drew a number from this repo's sequence.

| ID | Type | Slug | Closed | Closing SHA | Submitter | Resolution |
|---|---|---|---|---|---|---|

## Legacy — pre-sequence work

Work finished **before** this lifecycle existed. These rows are a record, not part of the
numbering sequence: they keep their original identifiers and paths, and they do **not**
participate in `max+1`. This section may preserve historical paths from before the handoff
ledger was installed.

| Original ID | Original path | Closed | Resolution |
|---|---|---|---|
