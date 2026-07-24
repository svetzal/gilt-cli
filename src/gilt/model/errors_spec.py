"""Specs for gilt.model.errors — domain error hierarchy."""

from __future__ import annotations

from pathlib import Path

from gilt.model.errors import (
    CONFIG_IO_ERRORS,
    DATA_IO_ERRORS,
    ConfigLoadError,
    GiltDataError,
    IntelligenceCacheError,
    LedgerLoadError,
)


class DescribeGiltDataError:
    def it_should_be_an_exception(self):
        exc = GiltDataError(Path("/some/file.csv"))
        assert isinstance(exc, Exception)

    def it_should_name_the_path_in_str(self):
        path = Path("/some/file.csv")
        exc = GiltDataError(path)
        assert str(path) in str(exc)


class DescribeConfigLoadError:
    def it_should_be_catchable_as_gilt_data_error(self):
        path = Path("/config/categories.yml")
        with _raises_gilt_data_error():
            raise ConfigLoadError(path)

    def it_should_name_the_path_in_str(self):
        path = Path("/config/categories.yml")
        exc = ConfigLoadError(path)
        assert str(path) in str(exc)


class DescribeLedgerLoadError:
    def it_should_be_catchable_as_gilt_data_error(self):
        path = Path("/data/accounts/MYBANK_CHQ.csv")
        with _raises_gilt_data_error():
            raise LedgerLoadError(path)

    def it_should_name_the_path_in_str(self):
        path = Path("/data/accounts/MYBANK_CHQ.csv")
        exc = LedgerLoadError(path)
        assert str(path) in str(exc)


class DescribeIntelligenceCacheError:
    def it_should_be_catchable_as_gilt_data_error(self):
        path = Path("/data/private/intelligence_cache.json")
        with _raises_gilt_data_error():
            raise IntelligenceCacheError(path)

    def it_should_name_the_path_in_str(self):
        path = Path("/data/private/intelligence_cache.json")
        exc = IntelligenceCacheError(path)
        assert str(path) in str(exc)


class DescribeErrorVocabulary:
    def it_should_expose_data_io_errors_covering_os_and_value_failures(self):
        assert isinstance(DATA_IO_ERRORS, tuple)
        assert all(isinstance(t, type) and issubclass(t, Exception) for t in DATA_IO_ERRORS)
        assert OSError in DATA_IO_ERRORS
        assert ValueError in DATA_IO_ERRORS

    def it_should_expose_config_io_errors_including_yaml_failures(self):
        assert isinstance(CONFIG_IO_ERRORS, tuple)
        assert all(isinstance(t, type) and issubclass(t, Exception) for t in CONFIG_IO_ERRORS)
        assert set(DATA_IO_ERRORS).issubset(set(CONFIG_IO_ERRORS))
        import yaml

        assert yaml.YAMLError in CONFIG_IO_ERRORS


import contextlib


@contextlib.contextmanager
def _raises_gilt_data_error():
    """Assert that the body raises GiltDataError (or a subclass)."""
    try:
        yield
        raise AssertionError("Expected GiltDataError to be raised")
    except GiltDataError:
        pass
