"""这个测试文件检查能力覆盖矩阵和帮助主题映射。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks the capability matrix and help-topic mapping. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

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
