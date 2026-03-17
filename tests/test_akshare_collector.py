import os

from app.collectors.akshare import _without_proxy_env


def test_without_proxy_env_temporarily_clears_proxy_variables() -> None:
    os.environ["HTTP_PROXY"] = "http://proxy.example"
    os.environ["HTTPS_PROXY"] = "http://proxy.example"

    with _without_proxy_env():
        assert "HTTP_PROXY" not in os.environ
        assert "HTTPS_PROXY" not in os.environ

    assert os.environ["HTTP_PROXY"] == "http://proxy.example"
    assert os.environ["HTTPS_PROXY"] == "http://proxy.example"
