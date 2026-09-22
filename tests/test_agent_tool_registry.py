from core.agent_tools import AgentToolRegistry, agent_tool_definitions
from core.external_tools import RestOpenApiBackend, ExternalToolError


def test_registry_exposes_requested_domains(tmp_path):
    reg = AgentToolRegistry([tmp_path], repo_root=tmp_path)
    names = {x["function"]["name"] for x in agent_tool_definitions()}
    expected = {
        "tool_catalog", "tool_describe", "tool_search",
        "list_files", "system_info", "network_interfaces", "list_services",
        "git_status", "runtime_inventory", "python_packages",
        "github_repo_info", "github_search_code",
        "http_get", "http_head", "openapi_inspect",
    }
    assert expected <= names
    assert len(names) == len(agent_tool_definitions())
    assert len(names) >= 35


def test_catalog_uses_canonical_metadata(tmp_path):
    reg = AgentToolRegistry([tmp_path], repo_root=tmp_path)
    catalog = reg.tool_catalog()
    assert catalog["count"] == len(agent_tool_definitions())
    by_name = {x["name"]: x for x in catalog["tools"]}
    assert by_name["git_status"]["risk_class"] == "READ_ONLY"
    assert by_name["github_repo_info"]["annotations"]["openWorldHint"] is True
    assert by_name["list_files"]["authorization_mode"] == "none"


def test_tool_search_finds_github(tmp_path):
    reg = AgentToolRegistry([tmp_path], repo_root=tmp_path)
    result = reg.tool_search("github")
    assert result["count"] >= 4
    assert all("github" in (x["name"] + x["source"]).lower() for x in result["matches"])


def test_rest_blocks_private_lan_target(monkeypatch):
    backend = RestOpenApiBackend()
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("192.168.1.10", 80))])
    try:
        backend._validate_url("http://example.internal/test")
        assert False, "private target should be blocked"
    except ExternalToolError as exc:
        assert "Private" in str(exc)


def test_rest_allows_loopback(monkeypatch):
    backend = RestOpenApiBackend()
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 5080))])
    assert backend._validate_url("http://127.0.0.1:5080/health").endswith("/health")


def test_mutating_and_execution_tools_are_not_exposed_yet():
    names = {x["function"]["name"] for x in agent_tool_definitions()}
    forbidden = {
        "write_file", "edit_file", "delete_file", "run_command",
        "git_commit", "git_push", "start_service", "stop_service",
        "http_post", "http_put", "http_patch", "http_delete",
    }
    assert names.isdisjoint(forbidden)
