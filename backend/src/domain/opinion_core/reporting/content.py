import hashlib
from datetime import datetime, timezone
from opinion_core.schemas.artifacts import ContentBlock, ContentBundle, EvidenceCard


def build_content(
    event_id,
    run_id,
    observations,
    evidence,
    versions,
    forum=None,
    prediction=None,
    scenarios=None,
    tools=None,
    recommendations=None,
):
    metrics = {
        "input_count": observations["input_n"],
        "missing_time_count": observations["missing_time_n"],
        "window_count": len(observations["windows"]),
        "joint_valid_count": sum(w["joint_n"] for w in observations["windows"]),
    }
    calc_id = "c-" + hashlib.sha256(str(sorted(versions.items())).encode()).hexdigest()
    calc = EvidenceCard(
        evidence_id=calc_id,
        kind="calculation",
        title="固定窗口与有效性掩码统计",
        excerpt="观测窗口、分母及字段状态来自确定性计算。",
        source_ref=versions["observations"],
        retrieved_at=datetime.now(timezone.utc),
        content_sha256=versions["observations"].removeprefix("a-"),
    )
    blocks = [
        ContentBlock(
            block_id="inventory",
            kind="observed",
            title="数据与覆盖",
            text="输入记录 {{input_count}} 条；发布时间缺失 {{missing_time_count}} 条；窗口 {{window_count}} 个；联合字段有效 {{joint_valid_count}} 条。",
            numeric_refs=list(metrics),
            evidence_refs=[calc_id],
        )
    ]
    for i, claim in enumerate((forum or {}).get("claims", [])):
        blocks.append(
            ContentBlock(
                block_id=f"interpretation-{i}",
                kind="interpretation",
                title="证据解释",
                text=claim["text"],
                evidence_refs=claim["evidence_refs"],
            )
        )
    if forum:
        last_host = (forum.get("rounds") or [{}])[-1].get("host", {})
        conflicts = last_host.get("conflicts", [])
        text = "讨论停止原因：" + forum["termination"] + "。"
        if conflicts:
            text += "\n保留分歧：" + "；".join(str(v) for v in conflicts)
        if forum.get("unresolved"):
            text += "\n未解决缺口：" + "；".join(str(v) for v in forum["unresolved"])
        blocks.append(
            ContentBlock(
                block_id="forum-status",
                kind="interpretation",
                title="讨论边界与分歧",
                text=text,
                artifact_refs=[versions["forum"]],
            )
        )
    for i, result in enumerate(tools or []):
        prefix = f"tool_{i}"
        metrics[prefix + "_selected"] = result["coverage"]["selected_n"]
        metrics[prefix + "_valid"] = result["coverage"]["valid_n"]
        blocks.append(
            ContentBlock(
                block_id=f"analysis-{i}",
                kind="observed",
                title=result["description"],
                text="筛选记录 {{"
                + prefix
                + "_selected}} 条；所需字段有效 {{"
                + prefix
                + "_valid}} 条。"
                + (
                    "计算结果见图表与来源表。"
                    if result["table"]
                    else "所需数据不足，未生成可解释结果。"
                )
                + " ".join(result["notes"]),
                numeric_refs=[prefix + "_selected", prefix + "_valid"],
                evidence_refs=[result["tool_id"]],
            )
        )
    for i, rec in enumerate((recommendations or {}).get("recommendations", [])):
        blocks.append(
            ContentBlock(
                block_id=f"recommendation-{i}",
                kind="simulated",
                title="情景建议：" + rec["scenario_id"],
                text=rec["rationale"]
                + "\n权衡："
                + rec["tradeoffs"]
                + "\n适用条件："
                + rec["conditions"],
                artifact_refs=[versions["scenarios"], versions["recommendations"]],
            )
        )
    if prediction and prediction.get("status") == "partial":
        blocks.append(
            ContentBlock(
                block_id="forecast-unavailable",
                kind="interpretation",
                title="预测尚不可用",
                text="缺少足够的联合有效观测，未生成模型预测；已保留可用的分布复盘结果。",
            )
        )
    elif prediction:
        metrics["forecast_horizon"] = len(prediction["steps"])
        blocks.append(
            ContentBlock(
                block_id="forecast",
                kind="forecast",
                title="实验性预测",
                text="预测 {{forecast_horizon}} 个窗口。区间为模型集合离散范围，尚未校准覆盖率。",
                numeric_refs=["forecast_horizon"],
                artifact_refs=[versions["forecast"]],
            )
        )
        if prediction["steps"]:
            last = prediction["steps"][-1]["fields"]
            metrics["final_stance_mean"] = last["stance"]["mean"]
            metrics["final_sentiment_mean"] = last["sentiment"]["mean"]
            blocks.append(
                ContentBlock(
                    block_id="forecast-final",
                    kind="forecast",
                    title="预测终点摘要",
                    text="实验模型终点立场均值 {{final_stance_mean}}，情绪均值 {{final_sentiment_mean}}；完整分布与集合范围见预测图表。",
                    numeric_refs=["final_stance_mean", "final_sentiment_mean"],
                    artifact_refs=[versions["forecast"]],
                )
            )
    if scenarios and scenarios.get("status") == "partial":
        blocks.append(
            ContentBlock(
                block_id="scenarios-unavailable",
                kind="interpretation",
                title="情景尚不可用",
                text="数值起点不可用，未生成条件情景。",
            )
        )
    elif scenarios:
        metrics["scenario_count"] = len(scenarios["branches"])
        blocks.append(
            ContentBlock(
                block_id="scenarios",
                kind="simulated",
                title="条件情景",
                text="构建 {{scenario_count}} 个情景分支；差异取决于模型与所列假设，不作为现实干预因果效应。",
                numeric_refs=["scenario_count"],
                artifact_refs=[versions["scenarios"]],
            )
        )
        for i, branch in enumerate(scenarios["branches"]):
            prefix = f"scenario_{i}"
            metrics[prefix + "_variance"] = branch["metrics"]["final_stance_variance"]
            metrics[prefix + "_change"] = branch["metrics"]["stance_variance_change"]
            metrics[prefix + "_cost"] = branch["metrics"]["resource_cost"]
            blocks.append(
                ContentBlock(
                    block_id=f"scenario-result-{i}",
                    kind="simulated",
                    title=branch["spec"]["measure"],
                    text="终点立场方差 {{"
                    + prefix
                    + "_variance}}；相对配对基线变化 {{"
                    + prefix
                    + "_change}}；资源成本 {{"
                    + prefix
                    + "_cost}}。\n假设："
                    + "；".join(branch["spec"]["assumptions"]),
                    numeric_refs=[
                        prefix + "_variance",
                        prefix + "_change",
                        prefix + "_cost",
                    ],
                    artifact_refs=[versions["scenarios"]],
                )
            )
    blocks.append(
        ContentBlock(
            block_id="limitations",
            kind="interpretation",
            title="方法与限制",
            text="模型弱标注自动进入分析。拒判、失败与缺失分别记录；真实模型质量、预测收益及图片增益需由后续独立评测确定。",
        )
    )
    unique = {e["evidence_id"]: e for e in evidence}
    unique[calc_id] = calc.model_dump(mode="json")
    return ContentBundle(
        event_id=event_id,
        run_id=run_id,
        blocks=blocks,
        evidence=list(unique.values()),
        metrics=metrics,
        source_versions=versions,
    ).model_dump(mode="json")
