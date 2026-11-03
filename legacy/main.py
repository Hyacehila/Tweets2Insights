"""
舆情分析智能体 - 主入口文件

系统采用线性主链模式，入口由 start_stage 控制。

================================================================================
使用说明
================================================================================

1. 在main()函数的配置区域修改参数
2. 运行 python main.py 启动系统
3. 系统会自动从 start_stage 进入并顺序执行剩余阶段

================================================================================
"""

import asyncio
import concurrent.futures
import time
import os
from dataclasses import asdict
from typing import Dict, Any, List

from flow import create_main_flow
from config import load_config, validate_config, config_to_shared, apply_glm_api_key
from utils.run_state import set_running
from utils.status_events import start_status_run


def init_shared(
    # 数据路径配置
    input_data_path: str = "data/beijing_rainstorm_posts.json",
    output_data_path: str = "data/enhanced_blogs.json",
    topics_path: str = "data/topics.json",
    sentiment_attributes_path: str = "data/sentiment_attributes.json",
    publisher_objects_path: str = "data/publisher_objects.json",
    belief_system_path: str = "data/believe_system_common.json",
    publisher_decision_path: str = "data/publisher_decision.json",
    # 管线配置
    start_stage: int = 1,
    # 阶段1配置
    enhancement_mode: str = "async",
    # 阶段2配置
    analysis_mode: str = "agent",
    tool_source: str = "mcp",
    agent_max_iterations: int = 10,
    chart_min_per_category: Dict[str, int] | None = None,
    chart_tool_policy: str = "coverage_first",
    chart_tool_allowlist: List[str] | None = None,
    # 阶段3配置
    report_max_iterations: int = 5,
    # 数据源配置
    data_source_type: str = "original",
) -> Dict[str, Any]:
    """
    初始化shared字典

    shared字典是节点间通信的核心数据结构，包含所有配置和运行时状态。
    主Flow会根据 start_stage 选择入口。

    Args:
        input_data_path: 输入博文数据文件路径
        output_data_path: 输出增强数据文件路径
        topics_path: 主题层次结构文件路径
        sentiment_attributes_path: 情感属性列表文件路径
        publisher_objects_path: 发布者类型列表文件路径
        start_stage: 起始阶段 (1/2/3)
        enhancement_mode: 阶段1处理模式 ("async")
        analysis_mode: 阶段2分析模式 ("agent")
        tool_source: Agent工具来源 ("mcp")
        agent_max_iterations: Agent最大迭代次数
        chart_min_per_category: 图表覆盖最低要求（按维度）
        chart_tool_policy: 图表覆盖策略
        chart_tool_allowlist: 图表工具白名单（可选）
        report_max_iterations: Stage3 章节评审最大轮次


    Returns:
        Dict: 初始化完成的shared字典
    """
    return {
        # === 数据管理（贯穿三阶段） ===
        "data": {
            "blog_data": [],              # 博文数据（原始或增强后）
            "topics_hierarchy": [],        # 主题层次结构（从data/topics.json加载）
            "sentiment_attributes": [],    # 情感属性列表（从data/sentiment_attributes.json加载）
            "publisher_objects": [],       # 发布者类型列表（从data/publisher_objects.json加载）
            "data_paths": {
                "blog_data_path": input_data_path,
                "topics_path": topics_path,
                "sentiment_attributes_path": sentiment_attributes_path,
                "publisher_objects_path": publisher_objects_path,
                "belief_system_path": belief_system_path,
                "publisher_decision_path": publisher_decision_path
            }
        },

        # === 管线状态（线性主链） ===
        "pipeline_state": {
            "start_stage": start_stage,    # 起始阶段：1 | 2 | 3
            "current_stage": 0,            # 当前执行到的阶段（0表示未开始）
            "completed_stages": [],        # 已完成的阶段列表
        },

        # === 三阶段路径控制（对应需求分析中的三阶段架构） ===
        "config": {
            # 阶段1: 增强处理方式（对应需求：四维度分析）
            "enhancement_mode": enhancement_mode,   # "async"
            # 阶段1: 断点续跑/防中断丢失（默认开启）
            # - enabled: 是否开启
            # - save_every: 每完成 N 条就保存一次（设为 1 即“每条都保存”）
            # - min_interval_seconds: 最小保存间隔（秒），避免过于频繁写盘
            "stage1_checkpoint": {
                "enabled": True,
                "save_every": 100,
                "min_interval_seconds": 20
            },

            # 阶段2: 分析执行方式（对应需求：分析工具集）
            "analysis_mode": analysis_mode,   # "agent"
            "tool_source": tool_source,          # "mcp" (Agent模式下的唯一工具来源)
            "stage2_chart": {
                "min_per_category": chart_min_per_category or {
                    "sentiment": 1,
                    "topic": 1,
                    "geographic": 1,
                    "interaction": 1,
                    "nlp": 1,
                },
                "tool_policy": chart_tool_policy,
                "tool_allowlist": list(chart_tool_allowlist or []),
            },

            # 阶段3: 统一报告评审配置
            "stage3_review": {
                "chapter_review_max_rounds": report_max_iterations,
            },

            # 阶段2 Agent配置
            "agent_config": {
                "max_iterations": agent_max_iterations
            },

            # 数据源配置
            "data_source": {
                "type": data_source_type,
                "resume_if_exists": True,
                "enhanced_data_path": output_data_path
            }
        },

        # === 阶段2运行时状态（Agent Loop模式） ===
        "agent": {
            "available_tools": [],         # 工具收集节点获取的可用工具列表
            "execution_history": [],       # 工具执行历史（每次循环记录）
            "current_iteration": 0,        # 当前循环迭代次数
            "max_iterations": agent_max_iterations,          # 最大迭代次数（防止无限循环）
            "is_finished": False           # Agent是否判断分析已充分
        },

        # === 阶段3报告生成状态 ===
        "report": {
            "iteration": 0,
            "current_draft": "",
            "revision_feedback": "",
            "review_history": []
        },

        # === 阶段1执行结果（由阶段1节点填充） ===
        "stage1_results": {
            # 数据统计信息（DataValidationAndOverviewNode填充）
            "statistics": {
                "total_blogs": 0,               # 总博文数
                "processed_blogs": 0,           # 已处理博文数（含增强字段）
                "empty_fields": {               # 增强字段空值统计
                    "sentiment_polarity_empty": 0,
                    "sentiment_attribute_empty": 0,
                    "topics_empty": 0,
                    "publisher_empty": 0
                },
                "engagement_statistics": {      # 参与度统计
                    "total_reposts": 0,
                    "total_comments": 0,
                    "total_likes": 0,
                    "avg_reposts": 0.0,
                    "avg_comments": 0.0,
                    "avg_likes": 0.0
                },
                "user_statistics": {            # 用户统计
                    "unique_users": 0,          # 独立用户数
                    "top_active_users": [],     # 活跃用户Top10
                    "user_type_distribution": {} # 发布者类型分布
                },
                "content_statistics": {         # 内容统计
                    "total_images": 0,
                    "blogs_with_images": 0,
                    "avg_content_length": 0.0,
                    "time_distribution": {}     # 按小时的发布时间分布
                },
                "geographic_distribution": {}   # 地理位置分布
            },
            # 数据保存状态（SaveEnhancedDataNode填充）
            "data_save": {
                "saved": False,
                "output_path": "",
                "data_count": 0
            }
        },

        # === 阶段2执行结果（由阶段2节点填充，存储到report/目录） ===
        "stage2_results": {
            # 生成的可视化图表列表
            "charts": [],
            # 生成的数据表格列表
            "tables": [],
            # LLM生成的深度洞察分析
            "insights": {
                "sentiment_insight": "",     # 情感趋势洞察
                "topic_insight": "",         # 主题演化洞察
                "geographic_insight": "",    # 地理分布洞察
                "cross_dimension_insight": "", # 多维交互洞察
                "summary_insight": ""        # 综合洞察摘要
            },
            # 分析执行记录
            "execution_log": {
                "tools_executed": [],        # 已执行的工具列表
                "total_charts": 0,           # 生成的图表总数
                "total_tables": 0,           # 生成的表格总数
                "execution_time": 0.0,       # 执行耗时（秒）
                "charts_by_category": {}     # 按维度统计图表数量
            },
            # 阶段2输出文件路径（供阶段3加载）
            "output_files": {
                "charts_dir": "report/images/",          # 图表存储目录
                "analysis_data": "report/analysis_data.json",  # 分析数据文件
                "insights_file": "report/insights.json"  # 洞察描述文件
            }
        },

        # === 阶段3执行结果（由阶段3节点填充） ===
        "stage3_results": {
            "report_file": "report/report.md",  # 最终报告文件路径
            "generation_mode": "",              # 生成模式：template | iterative
            "iterations": 0,                    # 迭代次数（iterative模式）
            "final_score": 0,                   # 最终评分（iterative模式）
            "report_reasoning": "",             # 报告编排的原因和逻辑说明
            "data_citations": {},               # 数据引用映射，确保结论有数据支撑
            "hallucination_check": {}           # 幻觉检测结果
        },

        # === LLM思考过程记录（Stage2和Stage3） ===
        "thinking": {
            "stage2_tool_decisions": [],        # Stage2工具调用决策思考
            "stage3_report_planning": [],       # Stage3报告编排思考
            "stage3_section_planning": {},      # 各章节具体编排思考
            "thinking_timestamps": []           # 思考过程时间戳
        }
    }


def print_banner():
    """打印程序启动横幅"""
    print("\n" + "=" * 60)
    print("舆情分析智能体系统".center(56))
    print("=" * 60)
    print("基于PocketFlow框架 | 线性主链模式")
    print("=" * 60 + "\n")


def print_config(shared: Dict[str, Any], concurrent_num: int, max_retries: int, wait_time: int):
    """打印配置信息"""
    start_stage = shared.get("pipeline_state", {}).get("start_stage", 1)
    execution_plan = [stage for stage in [1, 2, 3] if stage >= int(start_stage)]
    print("配置信息:")
    print(f"  ├─ 起始阶段: {start_stage}")
    print(f"  ├─ 执行链路: {execution_plan}")
    print(f"  ├─ 增强模式: {shared['config']['enhancement_mode']}")
    print(f"  ├─ 分析模式: {shared['config']['analysis_mode']}")
    stage3_review = shared["config"].get("stage3_review", {})
    print(
        "  ├─ Stage3评审: "
        f"max_rounds={stage3_review.get('chapter_review_max_rounds', 2)}"
    )
    print(f"  ├─ 输入路径: {shared['data']['data_paths']['blog_data_path']}")
    print(f"  ├─ 输出路径: {shared['config']['data_source']['enhanced_data_path']}")
    print(f"  ├─ 并发数: {concurrent_num}")
    print(f"  ├─ 重试次数: {max_retries}")
    print(f"  └─ 重试等待: {wait_time}秒")
    print()


def print_results(shared: Dict[str, Any], elapsed_time: float):
    """
    打印最终执行摘要

    注意：详细的数据统计信息已由 DataValidationAndOverviewNode 在阶段1完成时打印，
    此函数仅打印最终摘要信息（耗时、效率、保存状态）
    """
    print("\n" + "=" * 60)
    print("执行摘要".center(56))
    print("=" * 60)

    completed_stages = shared.get("pipeline_state", {}).get("completed_stages", [])
    print(f"\n[OK] 已完成阶段: {completed_stages}")

    # 数据保存状态（阶段1结果）
    data_save = shared.get("stage1_results", {}).get("data_save", {})
    if data_save.get("saved"):
        print(f"\n[DATA] 数据保存:")
        print(f"  ├─ 保存路径: {data_save.get('output_path', 'N/A')}")
        print(f"  └─ 保存数量: {data_save.get('data_count', 0)} 条")

    # 耗时和效率
    print(f"\n[TIME] 总耗时: {elapsed_time:.2f} 秒")

    stats = shared.get("stage1_results", {}).get("statistics", {})
    processed_blogs = stats.get('processed_blogs', 0)
    if processed_blogs > 0 and elapsed_time > 0:
        print(f"[RATE] 处理效率: {processed_blogs / elapsed_time:.2f} 条/秒")

    print("\n" + "=" * 60 + "\n")


async def run(
    shared: Dict[str, Any],
    concurrent_num: int = 60,
    max_retries: int = 3,
    wait_time: int = 8
):
    """
    运行主Flow - 系统唯一入口

    创建线性主Flow并运行。

    Args:
        shared: 初始化后的shared字典
        concurrent_num: 最大并发数
        max_retries: 最大重试次数
        wait_time: 重试等待时间（秒）
    """
    print_banner()
    print_config(shared, concurrent_num, max_retries, wait_time)

    # 设置线程池（用于异步调用同步LLM函数）
    thread_pool_size = concurrent_num + 20
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=thread_pool_size)
    loop = asyncio.get_running_loop()
    loop.set_default_executor(executor)
    print(f"[Main] 线程池配置: max_workers={thread_pool_size}")

    start_time = time.time()
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}\n")

    status_path = shared.get("status_file")
    status_doc = start_status_run(path=status_path if isinstance(status_path, str) and status_path.strip() else None)
    shared["status_run_id"] = status_doc.get("run_id", "")

    try:
        start_stage = int(shared.get("pipeline_state", {}).get("start_stage", 1))
        # 创建并运行主Flow - 入口由 start_stage 控制
        main_flow = create_main_flow(
            start_stage=start_stage,
            concurrent_num=concurrent_num,
            max_retries=max_retries,
            wait_time=wait_time
        )
        await main_flow.run_async(shared)

        elapsed_time = time.time() - start_time
        print_results(shared, elapsed_time)

    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n[X] 执行出错: {str(e)}")
        print(f"[T] 运行时间: {elapsed_time:.2f} 秒")
        import traceback
        traceback.print_exc()
        raise


def main():
    """
    主函数入口

    所有配置参数直接在此函数中修改。
    系统会根据 start_stage 配置自动执行对应阶段。
    """
    config = load_config("config.yaml")
    apply_glm_api_key(config)

    # Agent(MCP)模式下：MCP server 是独立子进程，需通过环境变量告知增强数据路径
    if config.stage2.mode == "agent" and config.stage2.tool_source == "mcp":
        if config.data.output_path:
            os.environ["ENHANCED_DATA_PATH"] = os.path.abspath(config.data.output_path)

    validate_config(config)
    shared = config_to_shared(config)

    set_running(True)
    try:
        asyncio.run(run(shared=shared, **asdict(config.runtime)))
    finally:
        set_running(False)


if __name__ == "__main__":
    main()
