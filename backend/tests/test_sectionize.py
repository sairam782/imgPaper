from app.ingest.sectionize import Section, sectionize, strip_references


def test_splits_numbered_headings():
    text = "\n".join(
        [
            "A Study of Things",
            "Jane Doe, John Roe",
            "Abstract",
            "We study things and find them interesting.",
            "1 Introduction",
            "Things have long been studied.",
            "2 Method",
            "We do the thing carefully.",
            "2.1 The Inner Loop",
            "The inner loop runs many times.",
        ]
    )
    paper = sectionize(text)
    headings = [s.heading for s in paper.sections]

    assert "Abstract" in headings
    assert "Introduction" in headings
    assert "The Inner Loop" in headings
    inner = next(s for s in paper.sections if s.heading == "The Inner Loop")
    assert inner.level == 2
    assert inner.number == "2.1"


def test_unnumbered_and_allcaps_headings():
    text = "Abstract\nbody one.\nMETHOD\nbody two.\nConclusion\nbody three."
    headings = [s.heading for s in sectionize(text).sections]
    assert headings == ["Abstract", "METHOD", "Conclusion"]


def test_numbers_starting_a_sentence_are_not_headings():
    text = "1 Introduction\n3 different models were compared in our study of the matter."
    paper = sectionize(text)
    assert [s.heading for s in paper.sections] == ["Introduction"]
    assert "3 different models" in paper.sections[0].text


def test_references_are_dropped():
    text = "1 Introduction\nbody.\nReferences\n[1] Someone. A paper. 2020."
    paper = sectionize(text)
    assert paper.dropped_references is True
    assert [s.heading for s in paper.sections] == ["Introduction"]
    assert "Someone" not in paper.sections[0].text


def test_references_can_be_kept():
    text = "1 Introduction\nbody.\nReferences\n[1] Someone. A paper. 2020."
    paper = sectionize(text, keep_references=True)
    assert paper.dropped_references is False
    assert "References" in [s.heading for s in paper.sections]


def test_strip_references_is_a_noop_without_them():
    sections = [Section("Introduction", "body")]
    kept, dropped = strip_references(sections)
    assert kept == sections
    assert dropped is False


def test_hyphenated_line_breaks_are_rejoined():
    text = "1 Method\nWe use self-atten-\ntion over the whole sequence."
    assert "self-attention over" in sectionize(text).sections[0].text


def test_title_spanning_two_lines_is_rejoined():
    text = "\n".join(
        [
            "Sparse Routing Improves Sample Efficiency",
            "in Small Language Models",
            "Ada Okonkwo, Rune Halvorsen",
            "Abstract",
            "We introduce sparse routing.",
        ]
    )
    assert sectionize(text).title_guess == (
        "Sparse Routing Improves Sample Efficiency in Small Language Models"
    )


def test_author_line_is_not_mistaken_for_a_title():
    text = "Ada Okonkwo, Rune Halvorsen, Priya Raghavan\nAbstract\nbody."
    assert sectionize(text).title_guess != "Ada Okonkwo, Rune Halvorsen, Priya Raghavan"


def test_roman_numeral_headings_are_parsed():
    text = "I Introduction\nbody one.\nIII Results\nbody two."
    paper = sectionize(text)
    assert [s.heading for s in paper.sections] == ["Introduction", "Results"]
    assert [s.number for s in paper.sections] == ["I", "III"]
    assert all(s.level == 1 for s in paper.sections)


def test_a_leading_roman_letter_is_not_stripped_from_a_word():
    # "C" is a roman numeral, so "Conclusion" and "Vision" must not lose it.
    text = "Conclusion\nWe conclude.\nVISION\nWe look ahead."
    assert [s.heading for s in sectionize(text).sections] == ["Conclusion", "VISION"]
