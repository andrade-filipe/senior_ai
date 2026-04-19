"""Infra tests — docker-compose.yml compliance (AC6–AC10, AC15, AC16).

All tests use yaml.safe_load — no Docker daemon required.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"

EXPECTED_SERVICES = {"ocr-mcp", "rag-mcp", "scheduling-api", "generated-agent"}

# Services that MUST have a healthcheck: block in compose
HEALTHCHECK_SERVICES = {"ocr-mcp", "rag-mcp", "scheduling-api"}


def _load_compose() -> dict:
    """Load and return the parsed compose file."""
    assert COMPOSE_PATH.exists(), f"docker-compose.yml missing at {COMPOSE_PATH}"
    with COMPOSE_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data


# ---------------------------------------------------------------------------
# [AC6] Four services with correct names
# ---------------------------------------------------------------------------
class TestAC6FourServices:
    """[AC6] docker-compose.yml declares exactly the four expected services."""

    def test_compose_declares_four_services(self) -> None:
        data = _load_compose()
        services = set(data.get("services", {}).keys())
        assert services == EXPECTED_SERVICES, (
            f"[AC6] Expected services {EXPECTED_SERVICES}; found {services}"
        )


# ---------------------------------------------------------------------------
# [AC7] Port exposure policy
# ---------------------------------------------------------------------------
class TestAC7PortExposure:
    """[AC7] Only scheduling-api publishes ports to the host."""

    def test_only_scheduling_api_publishes_port(self) -> None:
        data = _load_compose()
        services = data["services"]

        # scheduling-api must expose 8000:8000 (structural, not lexical — MINOR-1)
        sa_ports = services["scheduling-api"].get("ports", [])
        assert sa_ports, "[AC7] scheduling-api must publish ports (expected 8000:8000)."
        sa_ports_str = [str(p) for p in sa_ports]
        assert "8000:8000" in sa_ports_str, (
            f"[AC7] scheduling-api must publish exactly 8000:8000; found: {sa_ports_str}"
        )

        # MCPs and generated-agent must NOT have a ports: block
        for service in ("ocr-mcp", "rag-mcp", "generated-agent"):
            svc_ports = services[service].get("ports", [])
            assert not svc_ports, (
                f"[AC7] {service} must NOT publish any ports to the host; "
                f"found: {svc_ports}"
            )


# ---------------------------------------------------------------------------
# [AC8] scheduling-api healthcheck targets /health
# ---------------------------------------------------------------------------
class TestAC8HealthcheckHttp:
    """[AC8] scheduling-api healthcheck tests /health endpoint.

    DbC Post: healthcheck.test references /health (implies 200 OK if service is healthy).
    """

    def test_scheduling_api_has_health_healthcheck(self) -> None:
        data = _load_compose()
        hc = data["services"]["scheduling-api"].get("healthcheck", {})
        assert hc, "[AC8] scheduling-api must declare a healthcheck: block."
        test_cmd = str(hc.get("test", ""))
        assert "/health" in test_cmd, (
            f"[AC8] scheduling-api healthcheck must reference /health; found: {test_cmd!r}"
        )


# ---------------------------------------------------------------------------
# [AC9] generated-agent depends_on with correct conditions
# ---------------------------------------------------------------------------
class TestAC9DependsOn:
    """[AC9] generated-agent depends_on conditions per spec and ADR-0001."""

    def test_agent_depends_on_with_conditions(self) -> None:
        data = _load_compose()
        depends = data["services"]["generated-agent"].get("depends_on", {})
        assert depends, "[AC9] generated-agent must declare depends_on."

        # scheduling-api: service_healthy (API has /health endpoint)
        sa_cond = depends.get("scheduling-api", {}).get("condition")
        assert sa_cond == "service_healthy", (
            f"[AC9] generated-agent.depends_on.scheduling-api must be "
            f"service_healthy; found: {sa_cond!r}"
        )

        # MCPs: service_started (SSE has no native /health — ADR-0001)
        for mcp in ("ocr-mcp", "rag-mcp"):
            mcp_cond = depends.get(mcp, {}).get("condition")
            assert mcp_cond == "service_started", (
                f"[AC9] generated-agent.depends_on.{mcp} must be service_started; "
                f"found: {mcp_cond!r} (ADR-0001: MCPs use service_started)"
            )


# ---------------------------------------------------------------------------
# [AC10] generated-agent env uses compose DNS names (not localhost)
# ---------------------------------------------------------------------------
class TestAC10AgentEnv:
    """[AC10] generated-agent resolves MCP/API via compose DNS, not localhost."""

    def test_agent_env_matches_architecture_list(self) -> None:
        data = _load_compose()
        env = data["services"]["generated-agent"].get("environment", {})
        # Compose emits a dict here; we don't support the list form (the repo
        # convention is dict form, enforced by this assertion) — MINOR-4.
        assert isinstance(env, dict), (
            f"[AC10] generated-agent.environment must be a dict; got {type(env).__name__}"
        )
        env_dict = {k: str(v) for k, v in env.items()}

        expected = {
            "OCR_MCP_URL": "http://ocr-mcp:8001/sse",
            "RAG_MCP_URL": "http://rag-mcp:8002/sse",
            "SCHEDULING_OPENAPI_URL": "http://scheduling-api:8000/openapi.json",
        }
        for var, expected_val in expected.items():
            assert var in env_dict, (
                f"[AC10] generated-agent environment must declare {var}."
            )
            actual_val = env_dict[var]
            assert actual_val == expected_val, (
                f"[AC10] {var} must be {expected_val!r}; found {actual_val!r}. "
                "Use compose DNS names, not localhost."
            )


# ---------------------------------------------------------------------------
# [AC15] All healthcheck: blocks declare all four fields (DbC Invariant)
# ---------------------------------------------------------------------------
class TestAC15HealthcheckExplicit:
    """[AC15] Every healthcheck: in compose must declare interval, timeout,
    retries, and start_period explicitly — no implicit defaults.

    DbC Invariant: docker-compose.yml healthcheck: (ADR-0008 § Timeouts).
    """

    def test_healthcheck_fields_explicit(self) -> None:
        data = _load_compose()
        required_fields = {"interval", "timeout", "retries", "start_period"}

        for svc_name in HEALTHCHECK_SERVICES:
            svc = data["services"][svc_name]
            hc = svc.get("healthcheck", {})
            assert hc, (
                f"[AC15] {svc_name} must declare a healthcheck: block "
                "(explicit fields required by ADR-0008)."
            )
            missing = required_fields - set(hc.keys())
            assert not missing, (
                f"[AC15] {svc_name}.healthcheck missing fields: {missing}. "
                "All four fields must be explicit (interval, timeout, retries, "
                "start_period) — no implicit defaults (ADR-0008 § Timeouts)."
            )
            for field in required_fields:
                val = hc[field]
                assert val is not None and str(val).strip() != "", (
                    f"[AC15] {svc_name}.healthcheck.{field} must be a non-empty value."
                )

    def test_healthcheck_dockerfile_flags_via_regex(self) -> None:
        """[AC15] HEALTHCHECK instructions in Dockerfiles declare all four flags."""
        dockerfiles = {
            "ocr_mcp": REPO_ROOT / "ocr_mcp" / "Dockerfile",
            "rag_mcp": REPO_ROOT / "rag_mcp" / "Dockerfile",
            "scheduling_api": REPO_ROOT / "scheduling_api" / "Dockerfile",
        }
        required_flags = ("--interval=", "--timeout=", "--retries=", "--start-period=")
        for service, path in dockerfiles.items():
            assert path.exists(), f"[AC15] {path} not found."
            content = path.read_text(encoding="utf-8")
            hc_block = _extract_healthcheck_block(content)
            assert hc_block, (
                f"[AC15] {service}/Dockerfile must contain a HEALTHCHECK instruction."
            )
            for flag in required_flags:
                assert flag in hc_block, (
                    f"[AC15] {service}/Dockerfile HEALTHCHECK missing {flag!r}. "
                    "All four flags must be explicit (ADR-0008 § Timeouts)."
                )


def _extract_healthcheck_block(content: str) -> str:
    """Extract the HEALTHCHECK ... CMD ... line(s) from Dockerfile content."""
    lines = content.splitlines()
    hc_lines: list[str] = []
    in_hc = False
    for line in lines:
        stripped = line.rstrip()
        if re.match(r"^\s*HEALTHCHECK\b", stripped):
            in_hc = True
        if in_hc:
            hc_lines.append(stripped)
            if not stripped.endswith("\\"):
                break
    return " ".join(hc_lines)


# ---------------------------------------------------------------------------
# [AC16] No privileged, no docker socket, no network_mode host (DbC Invariant)
# ---------------------------------------------------------------------------
class TestAC16SecurityHardening:
    """[AC16] No service mounts docker socket, runs privileged, or uses host network.

    DbC Invariant: docker-compose.yml service (ADR-0008).
    """

    def test_no_privileged_or_docker_socket(self) -> None:
        data = _load_compose()
        services = data.get("services", {})

        for svc_name, svc in services.items():
            # No privileged: true
            assert svc.get("privileged") is not True, (
                f"[AC16] {svc_name} must not run privileged: true."
            )

            # No network_mode: host
            assert svc.get("network_mode") != "host", (
                f"[AC16] {svc_name} must not use network_mode: host."
            )

            # No docker socket volume mount
            volumes = svc.get("volumes", [])
            for vol in volumes:
                vol_str = str(vol)
                assert "/var/run/docker.sock" not in vol_str, (
                    f"[AC16] {svc_name} must not mount the Docker socket: {vol_str!r}"
                )
