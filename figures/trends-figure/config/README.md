# Configuration schema

Three files drive the pipeline. Code reads them; nobody hard-codes a search term.

- `corpus.yaml`    — the PubMed query that defines the paper pool, plus retrieval settings.
- `themes.yaml`    — term dictionary for the four themes.
- `modalities.yaml`— term dictionary for the fifteen modalities.

## Term dictionary schema

Both `themes.yaml` and `modalities.yaml` use one shape:

```yaml
version: 1                      # bump on any edit; recorded in run manifests
categories:
  <snake_case_key>:
    label: "Display Name"       # exact string used in figure axes
    type: "Imaging" | "Text" | null   # modalities only; null for themes
    include:                    # a record matches if ANY include pattern hits
      - pattern: "foundation model"
        kind: phrase | regex          # phrase = whitespace-tolerant literal, word-bounded
        case_sensitive: false         # optional; see "Matching" below
    exclude:                    # a record is rejected if ANY exclude pattern hits
      - pattern: "..."
        kind: phrase | regex
    notes: "Why these terms; what they deliberately miss."
```

## Matching

`trends.classify` matches these patterns against `title + " \n " + abstract`.

- `kind: phrase` — a literal. Word-bounded, **case-insensitive**, and tolerant of the
  amount of whitespace between its words. It does not match its own plural and it does not
  cross a hyphen: `digital twin` misses `digital twins`, `whole slide` misses
  `whole-slide`. Use a regex where either is wanted.
- `kind: regex` — a Python regular expression, compiled as written and therefore
  **case-sensitive**. Write `(?i)` at position 0 to opt into case-insensitivity; Python
  rejects a global inline flag anywhere else. This default is what makes bare acronyms
  usable: `\bCT\b` matches `chest CT` and not `qPCR Ct`.
- `case_sensitive: true | false` — optional, per pattern; omit it and the per-kind default
  above applies. On a phrase, `true` is the readable way to write an acronym
  (`pattern: "IHC"` matches `IHC`, not `ihc`). On a regex, `false` adds `re.IGNORECASE`.
  Setting `true` on a regex that already carries `(?i)` is a contradiction and is rejected.

A category is assigned when at least one `include` pattern hits and no `exclude` pattern
hits. Exclusion is category-level: it removes that one label from that one record, never
the record from the corpus. The schema ORs the `include` entries; write an AND as one regex
of anchored lookaheads, as `pathology_report` does.

Full detail, including what is checked at load and how to change a term safely, is in
`docs/classification.md`.

Rules:
- Every pattern needs a reason recorded in `notes` or in `docs/search-strategy.md`.
- Classification is multi-label: a paper may carry several themes and several modalities.
- `other` is **additive** and it does take include patterns. It means "uses a data type
  outside the named rows" — radiotherapy dose, dermoscopy, endoscopy, mass spectrometry and
  the like. It may appear alongside named modalities. The classifier also assigns it, as a
  fallback, to any record that matched no named modality at all.
