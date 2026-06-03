"""这个测试文件检查后续工程报告规则 schema 和模板。读测试时可以把每个断言看成一条项目承诺：输入什么、应该返回什么、哪些危险动作默认不能发生。

This test file checks future engineering report-rule schemas and templates. Read each assertion as one project promise: what input is accepted, what output must come back, and which risky actions must stay disabled by default.
"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_result_review_report_rule_template_matches_v1_1_contract() -> None:
    schema = json.loads((ROOT / "schemas" / "result_review_report_rules_v1_1.schema.json").read_text(encoding="utf-8"))
    template = json.loads((ROOT / "fixtures" / "result_review_report_rules_template_v1_1.json").read_text(encoding="utf-8"))

    assert schema["title"] == "ResultReviewReportRulesV1_1"
    assert template["object_type"] == "ResultReviewReportRules"
    assert template["schema_version"] == "1.1"
    assert template["status"] == "requires_user_thresholds"

    rule_keys = {rule["key"] for rule in template["rules"]}
    assert rule_keys == {
        "minimum_thickness",
        "thinning_ratio",
        "fld_risk",
        "springback_deviation",
        "maximum_force",
        "material_flow_abnormality",
    }
    assert all(rule["threshold"]["pass"] is None for rule in template["rules"])
    assert "minimum thickness pass, warning and fail limits" in template["required_user_inputs"]
    assert "threshold_rule_key" in template["annotation_rules"]["screenshot_caption_fields"]
