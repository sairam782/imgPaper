import os

from app.config import load_dotenv


def write_env(tmp_path, body):
    path = tmp_path / ".env"
    path.write_text(body, encoding="utf-8")
    return path


def test_reads_keys_values_quotes_and_comments(tmp_path, monkeypatch):
    monkeypatch.delenv("PP_TEST_KEY", raising=False)
    monkeypatch.delenv("PP_TEST_QUOTED", raising=False)
    monkeypatch.delenv("PP_TEST_EXPORTED", raising=False)

    load_dotenv(
        write_env(
            tmp_path,
            "# a comment\n"
            "\n"
            "PP_TEST_KEY=plain-value\n"
            'PP_TEST_QUOTED="quoted value"\n'
            "export PP_TEST_EXPORTED='exported'\n",
        )
    )

    assert os.environ["PP_TEST_KEY"] == "plain-value"
    assert os.environ["PP_TEST_QUOTED"] == "quoted value"
    assert os.environ["PP_TEST_EXPORTED"] == "exported"


def test_the_real_environment_wins(tmp_path, monkeypatch):
    # `ANTHROPIC_API_KEY=... make serve` must beat whatever the file says.
    monkeypatch.setenv("PP_TEST_PRECEDENCE", "from-the-shell")
    load_dotenv(write_env(tmp_path, "PP_TEST_PRECEDENCE=from-the-file\n"))
    assert os.environ["PP_TEST_PRECEDENCE"] == "from-the-shell"


def test_a_missing_file_is_not_an_error(tmp_path):
    load_dotenv(tmp_path / "nope.env")


def test_malformed_lines_are_skipped(tmp_path, monkeypatch):
    monkeypatch.delenv("PP_TEST_GOOD", raising=False)
    load_dotenv(write_env(tmp_path, "JUST_A_BARE_WORD\nPP_TEST_GOOD=yes\n"))

    assert os.environ["PP_TEST_GOOD"] == "yes"
    assert "JUST_A_BARE_WORD" not in os.environ


def test_a_value_containing_equals_is_kept_whole(tmp_path, monkeypatch):
    monkeypatch.delenv("PP_TEST_EQUALS", raising=False)
    load_dotenv(write_env(tmp_path, "PP_TEST_EQUALS=a=b=c\n"))
    assert os.environ["PP_TEST_EQUALS"] == "a=b=c"
