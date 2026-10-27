# Reusable library: local search-quality checkpoint

27 October 2026. This evaluates the local lexical search candidate on
`codex/companion-media-agent`, under the
[consolidated programme](2026-10-21-companion-media-agent-master-plan.md) and
[agent/library contract](2026-10-25-teaching-board-agent-build-plan.md).
It is engineering evidence using synthetic material, not teacher or classroom
acceptance. No provider, model, Hermes, network, handheld or paid image call is
needed. This does not close deployment or physical acceptance gates.

## Fixed evaluation set

[`board_search_quality.py`](../tools/compose/board_search_quality.py) declares
50 requests and their relevant resource keys independently of search results.
The disposable catalogue contains 20 synthetic resources: images, pages,
datasets, charts, documents, video metadata and audio metadata. Images contain
small generated colour blocks so local content hashes and availability can be
verified; their scientific correctness and thumbnail quality are not assessed.

Requests cover classroom phrasing, descriptions, corrected titles/tags, exact
remembered names, case/spacing, topic/year/type/review filters, rejected/excluded
defaults, ambiguous aliases, multiple exact versions and no-match requests.
There are 42 positive requests, of which 36 have one relevant version, and eight
negative requests. Five deliberately harder paraphrases and a generic-word
negative prevent a title-only success claim. A remembered preference is moved
from an older version to the chosen version in the fixture.

The benchmark preserves relevance sets and reports failures; it does not change
expected answers to match the ranker. A successful lexical match does not grant
approval or establish visual correctness. The automatic-selection guards remain
separate from these shortlist metrics.

## Reproduce locally

From the repository root, using the existing isolated Board environment:

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe tools/compose/board_search_quality.py --work-root .local --output .local/resource-library-search-quality.json
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tools/compose/tests/test_board_search_quality.py -q --tb=short --basetemp .local/pytest-board-search-quality
```

The CLI creates and removes its own temporary catalogue. `--work-root` supplies
an existing writable parent in restricted environments; it never opens an
existing library. `--output` records every query, expected/returned resource key,
filters, matching reasons, ranks and elapsed time in JSON. The output's parent
must exist. A reported quality gap does not make the command fail: the report
keeps experimental results reviewable while the separate tests enforce metric
arithmetic and exact-name/filter contracts.

## Measured result

The 27 October local run produced the following results. Timings measure one
warm local search per request, including opening SQLite and projecting records;
fixture creation is excluded. They are a small-catalogue observation, not a
performance target or a scale guarantee.

| Measure | Result |
| --- | --- |
| Mean recall within first five, positive requests | 98.81% |
| Mean reciprocal rank within first five, positive requests | 0.9881 |
| First result correct, single-choice requests | 35/36 (97.22%) |
| Mean precision amongst returned first five, positive requests | 75.36% |
| No-match requests returning an irrelevant result | 1/8 (12.50%) |
| Fully recalled positive requests or correctly empty negatives | 48/50 |
| Median search time | 2.114 ms |
| 95th-percentile search time, nearest rank | 4.839 ms |
| Focused metric/fixture/CLI tests | 4 passed in 1.69 s |

Recall is the fraction of declared relevant versions present in the shortlist.
Reciprocal rank is `1 / first relevant rank`, or zero when none is retrieved.
The precision measure divides relevant returned versions by the actual number
returned, up to five; it does not divide every request by five. No-match accuracy
is measured separately so a correct empty response cannot inflate positive
recall. Single-choice top-one measures the teacher's first result, whereas the
48/50 count only requires full recall somewhere in the shortlist.

Two full-recall/no-match gaps remain visible:

- “rain totals by month” returns the rainfall dataset and a water-cycle picture,
  missing the relevant rainfall chart. The literal words differ from “monthly
  rainfall”; lexical retrieval still needs teacher selection.
- “diagram of volcano layers” returns a water-cycle diagram because “diagram”
  overlaps. A generic resource word is weak evidence, and must not trigger
  automatic reuse or hidden generation.

Other positive requests can include irrelevant lower-ranked results. The
75.36% returned-result precision and 35/36 first-choice result expose this
despite high recall. No semantic index, embedding, cloud caption or broad
synonym expansion has been added to disguise the gaps.

## Next quality gate

Collect about 100 real teacher requests with teacher-declared relevant versions
and genuine no-match requests before selecting a more complex search method.
Keep some as a held-out set when tuning query words/ranking. Record corrections,
names, year/topic/type filters and approval states as they existed for each
judgement. Compare the current deterministic method against a candidate using
the same versions and relevance sets; report both misses and false suggestions.

The existing 1,000/10,000/100,000-record scale measurements remain open. Native
thumbnail/chooser checks, retention across restart/export, teacher usefulness,
actual lesson preparation time, deployment and classroom acceptance need their
own evidence and are not inferred from this synthetic benchmark.
