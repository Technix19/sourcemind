# Getting evaluation questions from ChatGPT

These questions are written by another AI, so they are tagged `"author": "external_llm"` and reported **separately** from the assistant's and the owner's. They are independent of both, which is the point, but they are not "owner-written".

## Steps
1. Start a **new** ChatGPT conversation (nothing about this project in it).
2. Attach the five PDFs from `data/evaluation/corpus/` (`nist-ai-rmf.pdf`, `nist-csf.pdf`, `nhlbi-sleep.pdf`, `fed-explained.pdf`, `us-constitution.pdf`).
3. Paste the prompt below.
4. Save ChatGPT's JSON answer as `data/evaluation/external_questions.json`.
5. `cd apps/api && source .venv/bin/activate && python -m evaluation.tools validate --file external_questions.json`
6. If some lines say `FIX`, copy **only those lines** back to ChatGPT and ask it to correct only those entries (see "Fixing" below), then re-validate.
7. Do not run the app or any search on these questions, and do not reword a question after seeing how a search handled it.

## The prompt (paste everything in the box)

```text
I am building an evaluation set for a document question-answering system. I have attached five PDF documents. Their ids are:

- nist-ai-rmf: NIST Artificial Intelligence Risk Management Framework 1.0
- nist-csf: NIST Cybersecurity Framework 2.0
- nhlbi-sleep: NIH "Your Guide to Healthy Sleep"
- fed-explained: Federal Reserve "The Fed Explained"
- us-constitution: The Constitution of the United States of America (House Document 110-50, with an analytical index)

TASK
Write exactly 10 questions that a real person might ask about these documents, and label each one precisely. Use only what is written in the attached documents. Do not use outside knowledge and do not browse the web.

MIX (exactly)
- 5 questions of type "paraphrase"
- 2 questions of type "specific"
- 1 question of type "direct"
- 1 question of type "unanswerable_related"
- 1 question of type "unanswerable_offtopic"
Cover at least four different documents, and use no more than three questions per document.

WHAT EACH TYPE MEANS
- paraphrase: the question's MEANING matches a passage, but its WORDS deliberately differ from the passage's wording, the way a real user who has not read the document would phrase it. Avoid reusing the passage's distinctive words and phrases. These are the most important questions.
- specific: asks for one concrete fact (a number, a name, a list item, a date).
- direct: reuses the document's own wording closely.
- unanswerable_related: a natural question about one document's topic whose answer is NOT stated anywhere in that document.
- unanswerable_offtopic: a question unrelated to all five documents.

RULES FOR ANSWERABLE QUESTIONS (paraphrase, specific, direct)
- Each must be answerable from a single passage of one document.
- Give "answer_spans": 1 to 3 phrases copied VERBATIM, character for character, from the document text, that directly state the answer. Each phrase must be 4 to 12 words long, contiguous, and must not cross a hyphenated line break, a table cell boundary or a column break. Do not use phrases containing special characters, ligatures or footnote numbers. If you cannot copy a phrase exactly, choose a different phrase or a different question. Never paraphrase inside "answer_spans".
- "doc" is the id of the document containing the answer.
- "answer" is a short plain-English answer (for humans only).
- Do not ask about a document's title, author, publication date or table of contents.

RULES FOR UNANSWERABLE QUESTIONS
- No "answer_spans".
- Give "absent_terms": 2 to 4 words or short phrases that WOULD appear in the document if it answered the question. Before finalising, search the relevant document and confirm that none of these terms appears in it. For unanswerable_related set "doc" to the document the question is about. For unanswerable_offtopic give 1 or 2 very distinctive words for the topic and omit "doc".
- Do not write trick questions. An unanswerable_related question must be something a reasonable user would genuinely expect the document might say.

GENERAL
- You cannot see any search system, and that is intended. Write the questions only from reading the documents.
- Make the questions different from each other, with varied wording and varied topics.
- Questions must be self-contained (do not say "according to the document" or refer to a page number).

OUTPUT
Return ONLY one valid JSON object, with no commentary before or after it and no Markdown code fence, in exactly this shape. Use "author": "external_llm" and ids "ext-01" to "ext-10". Field values below are examples of the FORMAT only:

{
  "dataset_version": "1",
  "corpus_version": "1",
  "questions": [
    {
      "id": "ext-01",
      "type": "paraphrase",
      "author": "external_llm",
      "question": "<a natural question in your own words>",
      "doc": "<one of the five ids>",
      "answer": "<short answer>",
      "answer_spans": ["<verbatim phrase 1>", "<verbatim phrase 2>"]
    },
    {
      "id": "ext-09",
      "type": "unanswerable_related",
      "author": "external_llm",
      "question": "<an on-topic question the document does not answer>",
      "doc": "<the document it is about>",
      "absent_terms": ["<term 1>", "<term 2>"]
    },
    {
      "id": "ext-10",
      "type": "unanswerable_offtopic",
      "author": "external_llm",
      "question": "<a question unrelated to all five documents>",
      "absent_terms": ["<distinctive word>"]
    }
  ]
}
```

## Fixing entries the validator rejects
Open a follow-up message in the same conversation and paste only the `FIX` lines, for example:

```text
My validator rejected these entries. Correct ONLY these entries and return the complete JSON object again, unchanged otherwise. For a phrase that "was not found in the corpus", copy a different short phrase that really appears verbatim in the document. Do not change the meaning or wording of any question.
<paste the FIX lines here>
```

Changing a *phrase* is fine (it only fixes a label). Do not change a *question* after you have seen how any search handled it.
