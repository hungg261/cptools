from cptools.lib.run import compare


class TestLineMode:
    def test_basic(self):
        assert compare("1 2 3\n", "1 2 3\n") is True

    def test_trailing_space_per_line(self):
        assert compare("1 2 3 \n4 5 6 ", "1 2 3\n4 5 6") is True

    def test_trailing_blank_lines(self):
        assert compare("1 2 3\n\n\n", "1 2 3\n") is True

    def test_crlf(self):
        assert compare("a\r\nb\r\n", "a\nb\n") is True

    def test_different_lines(self):
        assert compare("a b\nc d\n", "a b c d\n") is False

    def test_middle_blank_differs(self):
        assert compare("a\n\nb\n", "a\nb\n") is False

    def test_leading_space_matters(self):
        assert compare(" a\n", "a\n") is False

    def test_trailing_space_line_ignored(self):
        assert compare("a   \nb\n", "a\nb\n") is True


class TestTokenMode:
    def test_all_whitespace_collapsed(self):
        assert compare("1  2   3", "1 2 3", "token") is True

    def test_newlines_ignored(self):
        assert compare("1\n2\n3\n", "1 2 3", "token") is True

    def test_missing_token(self):
        assert compare("1 2", "1 2 3", "token") is False

    def test_extra_token(self):
        assert compare("1 2 3 4", "1 2 3", "token") is False

    def test_different_values(self):
        assert compare("1 2 4", "1 2 3", "token") is False


class TestExactMode:
    def test_identical(self):
        assert compare("a\nb\n", "a\nb\n", "exact") is True

    def test_trailing_newline_ignored(self):
        assert compare("a\nb", "a\nb\n", "exact") is True

    def test_whitespace_matters(self):
        assert compare("a  \nb\n", "a\nb\n", "exact") is False

    def test_leading_space_matters(self):
        assert compare(" a\n", "a\n", "exact") is False


class TestDefaultMode:
    def test_default_is_line(self):
        assert compare("a  \n", "a\n") is True

    def test_unknown_mode_falls_back_to_line(self):
        assert compare("a  \n", "a\n", "nonsense") is True