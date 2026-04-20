from pathlib import Path

import pytest

from gilt.model.raw_csv import read_raw_csv


@pytest.fixture
def tmp_csv(tmp_path):
    def _write(content: str, filename: str = "test.csv") -> Path:
        p = tmp_path / filename
        p.write_bytes(content.encode("utf-8-sig"))
        return p

    return _write


class DescribeReadRawCsv:
    class DescribeEncoding:
        def it_should_read_utf8_bom_file_correctly(self, tmp_csv):
            path = tmp_csv("name,value\nAlpha,1\n")

            df = read_raw_csv(path)

            assert list(df.columns) == ["name", "value"]
            assert df["name"].tolist() == ["Alpha"]

    class DescribeColumnTypes:
        def it_should_return_all_string_columns(self, tmp_csv):
            path = tmp_csv("amount,date\n-42.50,2024-01-15\n")

            df = read_raw_csv(path)

            assert df["amount"].iloc[0] == "-42.50"
            assert df["date"].iloc[0] == "2024-01-15"
            assert isinstance(df["amount"].iloc[0], str)
            assert isinstance(df["date"].iloc[0], str)

    class DescribeEmptyStrings:
        def it_should_preserve_empty_strings_not_nan(self, tmp_csv):
            path = tmp_csv("col_a,col_b\nfoo,\n,bar\n")

            df = read_raw_csv(path)

            assert df["col_b"].iloc[0] == ""
            assert df["col_a"].iloc[1] == ""
            assert not df.isnull().any().any()

    class DescribeNrows:
        def it_should_respect_nrows_limit(self, tmp_csv):
            path = tmp_csv("id\n1\n2\n3\n4\n5\n")

            df = read_raw_csv(path, nrows=3)

            assert len(df) == 3
            assert df["id"].tolist() == ["1", "2", "3"]

        def it_should_return_all_rows_when_nrows_is_none(self, tmp_csv):
            path = tmp_csv("id\n1\n2\n3\n")

            df = read_raw_csv(path, nrows=None)

            assert len(df) == 3
