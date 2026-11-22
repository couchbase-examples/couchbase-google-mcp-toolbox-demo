"""Offline checks for the agent route registry (no Couchbase, Toolbox or Gemini needed)."""
from pathlib import Path

import yaml

from src.agents.enhanced_manufacturing_agent import (
    DEFAULT_ROUTE_KEY,
    ROUTES,
    node_name_for,
    route_key_for,
)

TOOLS_YAML = Path(__file__).resolve().parents[1] / "tools.yaml"


def test_every_route_toolset_is_defined_in_tools_yaml():
    toolsets = yaml.safe_load(TOOLS_YAML.read_text())["toolsets"]
    missing = {key: r.toolset for key, r in ROUTES.items() if r.toolset not in toolsets}
    assert not missing, f"routes reference toolsets missing from tools.yaml: {missing}"


def test_streamlit_agent_types_route_to_their_own_agent():
    for query_type in ["general", "troubleshooting", "monitoring", "maintenance"]:
        assert route_key_for(query_type) == query_type


def test_unknown_query_type_falls_back_to_general():
    assert DEFAULT_ROUTE_KEY in ROUTES
    assert route_key_for("unknown") == DEFAULT_ROUTE_KEY
    assert route_key_for("") == DEFAULT_ROUTE_KEY


def test_node_names_are_unique():
    names = [node_name_for(key) for key in ROUTES]
    assert len(names) == len(set(names))
