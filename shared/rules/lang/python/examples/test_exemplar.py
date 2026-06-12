# Exemplar pytest module for the python-testing rule: imitate its shape
# (naming, fixtures, parametrization, property-based coverage), never its
# domain. The subject under test is inlined so the module runs as written;
# in a real repo it lives in the package and is imported.

import dataclasses
import datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st


# subject under test, inlined to keep the exemplar self-contained
@dataclasses.dataclass(frozen=True)
class Token:
    user: str
    expires_at: datetime.datetime


class ExpiredTokenError(Exception):
    pass


def validate(token: Token, now: datetime.datetime) -> str:
    if token.expires_at <= now:
        raise ExpiredTokenError(token.user)
    return token.user


NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


# fixtures carry shared arrange steps; narrowest scope that works
@pytest.fixture
def valid_token() -> Token:
    return Token(user="ada", expires_at=NOW + datetime.timedelta(hours=1))


# one behavior per test, named for the behavior; arrange, act, assert
# separated by blank lines, expected values as hand-computed constants
def test_accepts_unexpired_token(valid_token: Token):
    result = validate(valid_token, now=NOW)

    assert result == "ada"


def test_rejects_expired_token():
    token = Token(user="ada", expires_at=NOW - datetime.timedelta(seconds=1))

    with pytest.raises(ExpiredTokenError):
        validate(token, now=NOW)


# parametrize over loops in test bodies; ids name the non-obvious cases
@pytest.mark.parametrize(
    ("offset_seconds", "should_pass"),
    [(3600, True), (1, True), (0, False), (-3600, False)],
    ids=["one-hour-left", "one-second-left", "exactly-expired", "long-expired"],
)
def test_expiry_boundary(offset_seconds: int, should_pass: bool):
    token = Token(user="ada", expires_at=NOW + datetime.timedelta(seconds=offset_seconds))

    if should_pass:
        assert validate(token, now=NOW) == "ada"
    else:
        with pytest.raises(ExpiredTokenError):
            validate(token, now=NOW)


# property-based test for a pure function with a rich input space
@given(user=st.text(min_size=1))
def test_returns_user_verbatim_for_any_name(user: str):
    token = Token(user=user, expires_at=NOW + datetime.timedelta(hours=1))

    assert validate(token, now=NOW) == user
