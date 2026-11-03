import json

from evaluation import tools

PAGES = {"alpha": ["The six Functions are GOVERN,\nIDENTIFY and PROTECT.", "Quick-Start Guides are brief documents."], "beta": ["Quick-Start tips: be brief."]}


def test_find_is_case_and_line_break_insensitive_and_shows_context():
    out = tools.find(PAGES, "govern, identify")
    assert out[0].startswith("1 match") and "alpha p1" in out[1] and "[govern, identify]" in out[1]


def test_find_can_be_limited_to_one_document_and_reports_when_nothing_matches():
    assert tools.find(PAGES, "quick-start", doc="beta")[1].startswith("beta p1")
    assert len(tools.find(PAGES, "quick-start")) == 3                    # summary + two hits
    assert "No match" in tools.find(PAGES, "nothing like this")[0]
    assert tools.find(PAGES, "   ") == ["Type a phrase to look for."]


def test_find_caps_long_result_lists():
    many = {"d": ["common phrase here"] * 20}
    out = tools.find(many, "common phrase", limit=5)
    assert out[0].startswith("20 match") and out[-1] == "... and 15 more matches"


def test_page_viewer_validates_its_arguments():
    assert "page 2 of 2" in tools.show_page(PAGES, "alpha", 2)
    assert "Unknown document" in tools.show_page(PAGES, "gamma", 1) and "pages 1-2" in tools.show_page(PAGES, "alpha", 9)


def test_validation_report_is_friendly_and_specific(tmp_path):
    path = tmp_path / "blind_questions.json"
    assert "does not exist" in tools.check_file(PAGES, path)[0]
    path.write_text(json.dumps({"questions": []}))
    assert "no questions yet" in tools.check_file(PAGES, path)[0]
    path.write_text(json.dumps({"questions": [
        {"id": "owner-01", "type": "paraphrase", "author": "owner", "question": "What are the brief starter guides?", "doc": "alpha", "answer_spans": ["Quick-Start Guides are brief"]},
        {"id": "owner-02", "type": "specific", "author": "owner", "question": "What is the phone number of NIST?", "doc": "alpha", "answer_spans": ["555-0100"]},
    ]}))
    out = "\n".join(tools.check_file(PAGES, path))
    assert "OK    owner-01" in out and "relevant on 1 page" in out
    assert "FIX   owner-02" in out and "not found in the corpus" in out and "1 of 2 questions are valid" in out


def test_freezing_splits_labels_only_new_questions_and_never_moves_existing_ones(tmp_path):
    path = tmp_path / "q.json"
    base = {"id": "a", "type": "paraphrase", "author": "owner", "question": "A perfectly reasonable question?", "doc": "alpha",
            "answer_spans": ["Quick-Start Guides are brief"]}
    path.write_text(json.dumps({"questions": [{**base, "id": "old-1", "split": "test"}, {**base, "id": "old-2", "split": "test"}]}))
    assert "already has a frozen split" in tools.freeze_splits(path)[0]
    data = json.loads(path.read_text())
    data["questions"] += [{**base, "id": f"new-{i}"} for i in range(5)]
    path.write_text(json.dumps(data))
    message = tools.freeze_splits(path)[0]
    after = {x["id"]: x["split"] for x in json.loads(path.read_text())["questions"]}
    assert "Froze splits for 5 question(s)" in message and "3 dev, 2 test" in message
    assert after["old-1"] == after["old-2"] == "test"                       # untouched
    assert {after[f"new-{i}"] for i in range(5)} == {"dev", "test"}
    again = {x["id"]: x["split"] for x in (tools.freeze_splits(path), json.loads(path.read_text()))[1]["questions"]}
    assert again == after                                                   # idempotent
