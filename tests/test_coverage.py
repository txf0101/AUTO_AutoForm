import autoform_agent.coverage as coverage


def test_help_topic_agent_mapping_groups_topics(monkeypatch) -> None:
    monkeypatch.setattr(
        coverage,
        "list_help_topics",
        lambda query=None: [
            {"key": "MaterialEditor", "target": "/user-interface/material-generator-material-editor-viewer"},
            {"key": "ReportManager", "target": "/user-interface/reportmanager"},
            {"key": "Unknown", "target": "/other"},
        ],
    )

    mapping = coverage.help_topic_agent_mapping()

    assert mapping["topic_count"] == 3
    assert mapping["domain_counts"]["materials"] == 1
    assert mapping["domain_counts"]["reporting"] == 1
    assert mapping["domain_counts"]["unmapped"] == 1
    assert mapping["topics"][0]["agent_tools"][0] == "autoform_list_material_libraries"
