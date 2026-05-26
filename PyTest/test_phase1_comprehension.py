import sys
import os
import pytest

# Add project root to system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ai_tools
from database import DatabaseManager


@pytest.fixture(scope="module")
def project_dir():
    # Retrieve the last project dir from construction_costs.db
    db = DatabaseManager("construction_costs.db")
    path = db.get_setting('last_project_dir', '')
    if not path or not os.path.exists(path):
        # Fallback path if setting not configured
        path = "C:/Users/Consar-Kilpatrick/Desktop/Atlantic Catering School/Project Database"
    return path


def test_ingest_project_domains(project_dir):
    # Verify that domains ingestion completes without crash
    domains = ai_tools.ingest_project_domains(project_dir)
    assert isinstance(domains, dict)
    assert "project_settings" in domains
    assert "resources_summary" in domains
    assert "sor_data" in domains
    assert "pboq_summary" in domains
    assert "analytics_summary" in domains

    # Verify key metadata exists inside settings
    settings = domains["project_settings"]
    assert "project_name" in settings
    assert "base_currency" in settings
    assert "overhead_percent" in settings
    assert "profit_margin_percent" in settings

    # Verify PBOQ summary counts
    pboq = domains["pboq_summary"]
    assert pboq["total_items_count"] > 0
    assert pboq["priced_items_count"] > 0
    assert pboq["total_priced_value"] > 0
    assert "pricing_completeness_percent" in pboq


def test_wbs_parsing(project_dir):
    # Retrieve knowledge graph
    graph = ai_tools.build_unified_knowledge_graph(project_dir)
    assert isinstance(graph, dict)
    assert "wbs_hierarchy" in graph
    
    wbs = graph["wbs_hierarchy"]
    assert len(wbs) > 0
    
    # Verify that at least one priced sheet is captured with grouped sections
    some_sheet = list(wbs.keys())[0]
    sections = wbs[some_sheet]
    assert len(sections) > 0
    
    # Assert section keys correspond to valid construction categories
    valid_categories = {"Preliminaries", "Earthworks", "Concrete", "Formwork", "Reinforcement", "Blockwork", "Painting", "Plastering", "Miscellaneous"}
    assert any(cat in valid_categories for cat in sections.keys())


def test_recipe_coupling(project_dir):
    graph = ai_tools.build_unified_knowledge_graph(project_dir)
    assert "recipe_coupling" in graph
    
    coupling = graph["recipe_coupling"]
    # Verify that composite items are successfully coupled to their buildup estimates
    if len(coupling) > 0:
        first_item_name = list(coupling.keys())[0]
        recipe = coupling[first_item_name]
        
        assert "estimate_id" in recipe
        assert "net_total" in recipe
        assert "grand_total" in recipe
        assert "materials" in recipe
        assert "labor" in recipe


def test_resource_dependency_mapping(project_dir):
    graph = ai_tools.build_unified_knowledge_graph(project_dir)
    assert "resource_dependencies_warnings" in graph
    
    warnings = graph["resource_dependencies_warnings"]
    assert isinstance(warnings, list)
    
    # Verify warning fields if dependencies triggered warning logs
    for warning in warnings:
        assert "sheet" in warning
        assert "wbs_section" in warning
        assert "item" in warning
        assert "issue" in warning
        assert "severity" in warning
