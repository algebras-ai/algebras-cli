"""Retries of transient server and connection errors (502/503/504, timeouts)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from algebras.services.api_client import AlgebrasAIClient
from algebras.services.rate_limiter import RateLimiter
from algebras.services.retry_handler import RetryHandler


def _response(status_code, text="", headers=None, json_data=None):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.headers = headers or {}
    response.json.return_value = json_data or {}
    return response


def _handler(**kwargs):
    return RetryHandler(rate_limiter=RateLimiter(max_requests_per_minute=10_000), **kwargs)


def _calls(*outcomes):
    """api_call returning (or raising) each outcome in turn."""
    remaining = list(outcomes)
    calls = []

    def api_call():
        calls.append(1)
        outcome = remaining.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    return api_call, calls


@pytest.mark.parametrize("status_code", [502, 503, 504])
def test_gateway_error_is_retried(status_code):
    api_call, calls = _calls(_response(status_code, "<html>502</html>"), _response(200))

    with patch("time.sleep") as sleep:
        result = _handler().execute_with_retry(api_call)

    assert result.status_code == 200
    assert len(calls) == 2
    assert sleep.call_count == 1


def test_gateway_error_retries_are_bounded():
    api_call, calls = _calls(*[_response(502, "Bad Gateway")] * 4)

    with patch("time.sleep"):
        with pytest.raises(Exception, match="Error from Algebras AI API: 502 - Bad Gateway"):
            _handler(transient_retries=3).execute_with_retry(api_call)

    assert len(calls) == 4  # first attempt + 3 retries


def test_gateway_error_backoff_grows():
    api_call, _ = _calls(*[_response(504)] * 3, _response(200))

    with patch("time.sleep") as sleep, patch("random.uniform", return_value=0):
        _handler(transient_initial_wait=2.0).execute_with_retry(api_call)

    assert [c.args[0] for c in sleep.call_args_list] == [2.0, 6.0, 18.0]


def test_retry_after_header_is_honored_and_capped():
    api_call, _ = _calls(
        _response(503, headers={"Retry-After": "7"}),
        _response(503, headers={"Retry-After": "600"}),
        _response(200),
    )

    with patch("time.sleep") as sleep, patch("random.uniform", return_value=0):
        _handler(transient_max_wait=30.0).execute_with_retry(api_call)

    assert [c.args[0] for c in sleep.call_args_list] == [7.0, 30.0]


@pytest.mark.parametrize(
    "error", [requests.exceptions.ConnectionError("reset"), requests.exceptions.ReadTimeout("slow")]
)
def test_connection_error_is_retried(error):
    api_call, calls = _calls(error, _response(200))

    with patch("time.sleep"):
        result = _handler().execute_with_retry(api_call)

    assert result.status_code == 200
    assert len(calls) == 2


def test_connection_error_retries_are_bounded():
    api_call, calls = _calls(*[requests.exceptions.ConnectionError("reset")] * 3)

    with patch("time.sleep"):
        with pytest.raises(Exception, match="Request failed: reset"):
            _handler(transient_retries=2).execute_with_retry(api_call)

    assert len(calls) == 3


def test_internal_server_error_is_not_retried():
    api_call, calls = _calls(_response(500, "boom"))

    with pytest.raises(Exception, match="Error from Algebras AI API: 500 - boom"):
        _handler().execute_with_retry(api_call)

    assert len(calls) == 1


def test_other_request_errors_are_not_retried():
    api_call, calls = _calls(requests.exceptions.InvalidURL("bad url"))

    with pytest.raises(Exception, match="Request failed: bad url"):
        _handler().execute_with_retry(api_call)

    assert len(calls) == 1


def test_client_errors_are_returned_without_retry():
    api_call, calls = _calls(_response(401, "unauthorized"))

    assert _handler().execute_with_retry(api_call).status_code == 401
    assert len(calls) == 1


def test_rate_limit_and_gateway_retries_are_counted_separately():
    api_call, calls = _calls(
        _response(429), _response(502), _response(429), _response(502), _response(200)
    )

    with patch("time.sleep"):
        result = _handler(max_retries=2, transient_retries=2).execute_with_retry(api_call)

    assert result.status_code == 200
    assert len(calls) == 5


# --- Polling translate-batch-async jobs -----------------------------------------------


def _client():
    return AlgebrasAIClient(MagicMock(), _handler())


def _job(status, **extra):
    return _response(200, json_data={"data": {"status": status, **extra}})


def test_poll_retries_gateway_errors():
    responses = [_response(502), _response(504), _job("READY", result={"ok": True})]

    with patch("algebras.services.api_client.requests.get", side_effect=responses), patch(
        "algebras.services.api_client.time.sleep"
    ):
        result = _client()._poll_batch_job("job-1", {}, "https://example.test")

    assert result == {"ok": True}


def test_poll_gives_up_after_consecutive_gateway_errors():
    responses = [_response(502, "Bad Gateway")] * 6

    with patch("algebras.services.api_client.requests.get", side_effect=responses), patch(
        "algebras.services.api_client.time.sleep"
    ):
        with pytest.raises(Exception, match="job-1: 502 - Bad Gateway"):
            _client()._poll_batch_job("job-1", {}, "https://example.test")


def test_poll_gateway_error_count_resets_after_a_good_response():
    responses = (
        [_response(502)] * 5 + [_job("PROCESSING")] + [_response(502)] * 5 + [_job("READY", result={})]
    )

    with patch("algebras.services.api_client.requests.get", side_effect=responses), patch(
        "algebras.services.api_client.time.sleep"
    ):
        assert _client()._poll_batch_job("job-1", {}, "https://example.test") == {}


def test_poll_does_not_retry_internal_server_error():
    with patch(
        "algebras.services.api_client.requests.get", side_effect=[_response(500, "boom")]
    ), patch("algebras.services.api_client.time.sleep"):
        with pytest.raises(Exception, match="job-1: 500 - boom"):
            _client()._poll_batch_job("job-1", {}, "https://example.test")
