import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from expand_lyrics import expand, main  # noqa: E402


def test_no_markers_unchanged():
    assert expand("a\nb\n\nc\n") == "a\nb\n\nc\n"


def test_whole_stanza_repeated():
    assert expand("a\nb /x2\n") == "a\nb\na\nb\n"


def test_lines_after_marker_kept_once():
    assert expand("a\nb /X3\nkoniec\n") == "a\nb\na\nb\na\nb\nkoniec\n"


def test_crlf_and_multiple_stanzas():
    text = "z1\r\n\r\nr1\r\nr2 /x2\r\n\r\nz2\r\n"
    assert expand(text) == "z1\n\nr1\nr2\nr1\nr2\n\nz2\n"


def test_cli(tmp_path, capsys):
    src, dst = tmp_path / "in.txt", tmp_path / "out.txt"
    src.write_text("Zażółć /x2\n", encoding="utf-8")
    assert main([str(src), str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "Zażółć\nZażółć\n"
    assert main([]) == 1


def test_cli_creates_missing_output_dir(tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("a\n", encoding="utf-8")
    dst = tmp_path / "nowy" / "out.txt"
    assert main([str(src), str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "a\n"
