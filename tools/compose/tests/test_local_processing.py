import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from assistant_service import AssistantService
from llm_pipeline import LlmPipeline
from local_processing import local_request


@pytest.mark.parametrize("host", ["https://remote.invalid", "http://100.64.0.8:11434",
                                  "http://127.0.0.1@remote.invalid:11434"])
def test_local_only_assistant_and_compose_refuse_remote_ollama_before_http(host):
    service = AssistantService({"LOCAL_ONLY": "1", "OLLAMA_HOST": host}, lambda: {}, None)
    with patch.object(service.session, "post") as post:
        assert not service.reply("Private selected text")["ok"]
        post.assert_not_called()
    pipeline = LlmPipeline(local_only=True, ollama_host=host)
    with patch("local_processing.requests.Session") as session:
        with pytest.raises(ValueError, match="loopback"):
            pipeline.generate([{"role": "user", "content": "Private selected text"}])
        session.assert_not_called()


def test_local_model_disables_proxy_discovery_and_refuses_redirect():
    response = Mock(status_code=302)
    with patch("local_processing.requests.Session") as factory:
        session = factory.return_value.__enter__.return_value
        session.request.return_value = response
        with pytest.raises(ValueError, match="redirect"):
            local_request("POST", "http://127.0.0.1:11434/v1/chat/completions", json={})
        assert session.trust_env is False
        assert session.request.call_args.kwargs["allow_redirects"] is False


def test_loopback_local_model_response_remains_usable():
    response = Mock(status_code=200)
    with patch("local_processing.requests.Session") as factory:
        factory.return_value.__enter__.return_value.request.return_value = response
        assert local_request("GET", "http://localhost:11434/api/tags") is response
