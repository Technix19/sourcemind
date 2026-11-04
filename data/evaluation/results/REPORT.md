# Retrieval evaluation report

Held-out **test** split, scored once on 2026-11-04 at commit `0db61d1` (clean working tree). 19 questions (15 answerable, 4 unanswerable); 1345 chunks of 950 characters.

Values are means with 95% bootstrap intervals in parentheses. **If two intervals overlap, no difference is demonstrated.**

## Read this first

- Small sample: 15 answerable and 4 unanswerable test questions. Every figure has a wide 95% interval; overlapping intervals mean no demonstrated difference.
- A single author wrote all questions (the project assistant); there is no independent-author check, and wording bias toward keyword search cannot be ruled out.
- Five public-domain US government documents; the results may not transfer to other kinds of documents.
- The test split was scored once, after the thresholds and chunk size were frozen on the development split (see the pre-registered plan).
- An interval such as 1.00 (1.00-1.00) is NOT certainty: a percentile bootstrap collapses to a point whenever every question agrees, which with only a handful of questions says little. The true uncertainty is larger (this is most visible in the abstention rows, which rest on 4 questions).
- Retrieval only: this measures whether the right page is found, not whether generated answers are correct.

## Ranking quality (threshold-free)

| Method | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|
| Keyword (TF-IDF) | 0.40 (0.20-0.67) | 0.60 (0.33-0.80) | 0.73 (0.47-0.93) | 0.53 (0.35-0.73) |
| Meaning (embeddings) | 0.60 (0.33-0.87) | 0.87 (0.67-1.00) | 0.93 (0.80-1.00) | 0.75 (0.57-0.90) |
| Hybrid (experimental) | 0.60 (0.33-0.80) | 0.93 (0.80-1.00) | 0.93 (0.80-1.00) | 0.76 (0.60-0.90) |

### Recall@3 by question type

| Type | Keyword (TF-IDF) | Meaning (embeddings) | Hybrid (experimental) |
|---|---|---|---|
| direct (n=2) | 1.00 (1.00-1.00) | 1.00 (1.00-1.00) | 1.00 (1.00-1.00) |
| paraphrase (n=7) | 0.43 (0.14-0.86) | 0.86 (0.57-1.00) | 0.86 (0.57-1.00) |
| specific (n=6) | 0.67 (0.33-1.00) | 0.83 (0.50-1.00) | 1.00 (1.00-1.00) |

## Saying "not enough evidence"

Thresholds were tuned on the development split: keyword **0.25**, meaning **0.7**. The product's current defaults are 0.05 and 0.5. Only 4 unanswerable test questions exist, so abstention intervals are very wide.

| Method | Setting | Correct abstention | False abstention | End-to-end Recall@3 |
|---|---|---|---|---|
| Keyword (TF-IDF) | tuned | 1.00 (1.00-1.00) | 0.67 (0.40-0.87) | 0.33 (0.13-0.60) |
| Keyword (TF-IDF) | product defaults | 0.00 (0.00-0.00) | 0.00 (0.00-0.00) | 0.60 (0.33-0.80) |
| Meaning (embeddings) | tuned | 0.50 (0.00-1.00) | 0.13 (0.00-0.33) | 0.67 (0.40-0.87) |
| Meaning (embeddings) | product defaults | 0.25 (0.00-0.75) | 0.00 (0.00-0.00) | 0.87 (0.67-1.00) |
| Hybrid (experimental) | tuned | 0.50 (0.00-1.00) | 0.13 (0.00-0.33) | 0.80 (0.60-1.00) |
| Hybrid (experimental) | product defaults | 0.00 (0.00-0.00) | 0.00 (0.00-0.00) | 0.93 (0.80-1.00) |

## Recommendation

Meaning (embeddings) and Hybrid (experimental) met the pre-registered condition for RECOMMENDING a change of default (higher Recall@3 and MRR, balanced accuracy not lower), but no difference is demonstrated: the 95% intervals overlap. This is a judgment call for the project owner, not a measured win.

## Chunk size (development split)

| Size / overlap | Chunks | Keyword Recall@3 | Meaning Recall@3 |
|---|---|---|---|
| 500/90 | 2412 | 0.67 (0.44-0.89) | 0.78 (0.61-0.94) |
| 950/170 | 1345 | 0.67 (0.44-0.89) | 0.78 (0.56-0.94) |
| 1500/270 | 887 | 0.67 (0.44-0.89) | 0.78 (0.56-0.94) |

The pre-registered rule keeps 950 characters unless another size wins on both Recall@3 and MRR by at least 0.10; none did.

## Failure analysis

Written AFTER the held-out test split was scored. It is descriptive only: no retrieval code, threshold, label or question was changed in response to it (pre-registered rule 5).

### Keyword search fails when the question's words differ from the passage's

Recall@3 on paraphrase questions: keyword 0.43, meaning 0.86 (7 questions; the intervals overlap, so this is suggestive, not demonstrated).

### Meaning search's typical error is a topical neighbor, not noise

Its wrong top hits were real, related passages (the Constitution's qualification ages instead of the voting age; the Cybersecurity Framework's 'resilience of technology infrastructure' instead of the AI framework's resilience definition; the FOMC's membership page instead of its meeting schedule). Plausible-looking wrong evidence is harder for a reader to spot than an obviously irrelevant hit.

### Meaning search cannot tell 'related but unanswerable' from a real answer

Best similarity: both related-but-unanswerable questions scored 0.74, inside the 0.68-0.88 range of real answers; off-topic questions scored 0.49-0.53. A threshold can reject off-topic questions but not on-topic questions whose answer is absent. Only 4 unanswerable test questions exist, so every abstention number has a very wide interval.

### The keyword score cannot be gated usefully

At its tuned threshold (0.25) keyword search abstained correctly on all 4 unanswerable questions but also refused 10 of 15 answerable ones; at the old default (0.05) it never abstained. Keyword scores do not separate 'no answer' from 'weak answer'.

### Thresholds tuned on the development split generalized worse than they looked

Meaning search's correct abstention fell from 0.75 (dev, where it was tuned) to 0.50 (test); its end-to-end Recall@3 at the tuned threshold was 0.67 on test versus 0.87 at the old default. Tuning on a few dozen questions overfits; the test split exists to show exactly this.

### PDF layout noise is a separate source of error

Two-column tables are extracted with the columns interleaved, which scrambles sentences. On the development split meaning search missed a direct question whose answer sat in such a table; the same table page was found in the test run, so this is an observation, not a measured rate.

### Label limitations

- **con-04**: The Constitution edition includes an analytical index that restates provisions. For the Second Amendment, index pages 75 and 54 quote the text with different capitalization and punctuation ('arms shall' instead of 'Arms, shall'), so my literal answer phrase matched only the amendment's own page (19). Meaning search put the index pages first; they genuinely state the answer, but the frozen labels count them as wrong. The reported miss therefore overstates the failure. Labels were not changed after the test run (pre-registered).

### Individual misses (rank of the first correct page)

- **con-03** (adjacent topic; keyword 7, meaning 2, hybrid 1): Keyword search matched pages that merely share words with the question (an index entry about a majority vote). Meaning search ranked the index entries for senator and representative qualifications (ages thirty and twenty-five) first: right kind of rule, wrong rule. The answer page was second.
- **con-04** (label gap; keyword 3, meaning 9, hybrid 3): See the label limitation above: the pages ranked first are index entries that restate the Second Amendment.
- **csf-03** (vocabulary gap; keyword 15, meaning 3, hybrid 8): The question never mentions 'gap', 'Profile' or 'action plan', the words on the answer page. Keyword search returned generic framework overview pages. Meaning search returned the Tiers appendix pages (organizational posture) and found the answer third.
- **fed-04** (vocabulary gap; keyword 12, meaning 1, hybrid 2): Keyword search matched 'central bank' in the document's repeated title pages. Meaning search understood that 'territories cutting across state boundaries' means the Federal Reserve Districts.
- **x-02** (adjacent topic; keyword 10, meaning 2, hybrid 2): Keyword search matched the words 'protect', 'attacks' and 'recover' in the Cybersecurity Framework. Meaning search ranked a Cybersecurity Framework passage about the resilience of technology infrastructure first (a different document) and the correct AI-framework definition second.
- **x-06** (adjacent topic; keyword 4, meaning 4, hybrid 2): All methods ranked the FOMC membership page above the page that states 'eight regularly scheduled joint meetings'. That membership page does not mention how often the committee meets: it is the right topic and the wrong passage. A true miss.
- **x-08** (vocabulary gap; keyword 5, meaning 1, hybrid 2): Keyword search latched onto isolated words ('tax' in a clause about importing slaves, 'election' in vacancy rules). The question says 'fee to vote'; the text says 'poll tax'. Meaning search got it first.

## Not measured

- Citation accuracy and faithfulness of generated answers (needs a language-model key; retrieval only is measured here).
- Production latency: the figures here exclude network and database time, and the product refits keyword search per query.
- Different document types, languages, scanned PDFs, or very large libraries.
