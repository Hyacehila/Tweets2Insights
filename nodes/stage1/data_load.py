"""
Stage 1 data loading node.
"""
import os
from typing import Any, Dict

from nodes.base import MonitoredNode

from utils.data_loader import (
    load_blog_data,
    load_topics,
    load_sentiment_attributes,
    load_publisher_objects,
    load_enhanced_blog_data,
    load_belief_system,
)
from utils.data_sources.json_source import JsonDataSource


class DataLoadNode(MonitoredNode):
    """
    数据加载节点

    功能：加载原始博文数据或已增强的数据
    类型：Regular Node
    """

    def prep(self, shared):
        """读取数据文件路径和配置参数"""
        config = shared.get("config", {})
        data_paths = shared.get("data", {}).get("data_paths", {})

        data_source_type = config.get("data_source", {}).get("type", "original")
        enhanced_data_path = config.get("data_source", {}).get("enhanced_data_path", "data/enhanced_blogs.json")

        if data_source_type == "enhanced":
            enhanced_data_path = config.get("data_source", {}).get(
                "enhanced_data_path", "data/enhanced_blogs.json"
            )
            return {
                "load_type": "enhanced",
                "data_path": enhanced_data_path,
            }

        return {
            "load_type": "original",
            "blog_data_path": data_paths.get("blog_data_path", "data/beijing_rainstorm_posts.json"),
            "enhanced_data_path": enhanced_data_path,
            "resume_if_exists": config.get("data_source", {}).get("resume_if_exists", True),
            "topics_path": data_paths.get("topics_path", "data/topics.json"),
            "sentiment_attributes_path": data_paths.get("sentiment_attributes_path", "data/sentiment_attributes.json"),
            "publisher_objects_path": data_paths.get("publisher_objects_path", "data/publisher_objects.json"),
            "belief_system_path": data_paths.get("belief_system_path", "data/believe_system_common.json"),
        }

    def exec(self, prep_res):
        """加载JSON格式数据，验证格式完整性"""
        source = JsonDataSource(loaders={
            "load_blog_data": load_blog_data,
            "load_enhanced_blog_data": load_enhanced_blog_data,
            "load_topics": load_topics,
            "load_sentiment_attributes": load_sentiment_attributes,
            "load_publisher_objects": load_publisher_objects,
            "load_belief_system": load_belief_system,
        })

        if prep_res["load_type"] == "enhanced":
            enhanced_data = source.load_enhanced_data(prep_res["data_path"])
            return {
                "blog_data": enhanced_data,
                "load_type": "enhanced",
            }

        blog_data = source.load_blog_data(prep_res["blog_data_path"])

        # 如果存在上次运行的增强输出，则优先加载以便断点续跑
        enhanced_data_path = prep_res.get("enhanced_data_path")
        if prep_res.get("resume_if_exists", True) and enhanced_data_path and os.path.exists(enhanced_data_path):
            try:
                enhanced_data = source.load_enhanced_data(enhanced_data_path)

                def _same_post(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
                    for k in ("content", "publish_time", "user_id", "username"):
                        if a.get(k) != b.get(k):
                            return False
                    return True

                if len(enhanced_data) == len(blog_data) and len(blog_data) > 0:
                    sample_indices = {0, len(blog_data) // 2, len(blog_data) - 1}
                    matches = sum(
                        1 for i in sample_indices
                        if _same_post(blog_data[i], enhanced_data[i])
                    )
                    if matches >= max(1, len(sample_indices) - 1):
                        blog_data = enhanced_data
                        print(f"[DataLoad] Resume enabled: loaded existing enhanced data: {enhanced_data_path}")
                    else:
                        print(f"[DataLoad] Resume skipped: enhanced file does not match input dataset: {enhanced_data_path}")
                else:
                    print(f"[DataLoad] Resume skipped: enhanced file length mismatch: {enhanced_data_path}")
            except Exception as e:
                print(f"[DataLoad] Resume skipped: failed to load enhanced file: {enhanced_data_path}, err={e}")

        return {
            "blog_data": blog_data,
            "topics_hierarchy": source.load_topics(prep_res["topics_path"]),
            "sentiment_attributes": source.load_sentiment_attributes(prep_res["sentiment_attributes_path"]),
            "publisher_objects": source.load_publisher_objects(prep_res["publisher_objects_path"]),
            "belief_system": source.load_belief_system(prep_res["belief_system_path"]),
            "load_type": "original",
        }

    def post(self, shared, prep_res, exec_res):
        """将数据存储到shared中"""
        if "data" not in shared:
            shared["data"] = {}

        shared["data"]["blog_data"] = exec_res["blog_data"]
        shared["data"]["load_type"] = exec_res["load_type"]

        if exec_res["load_type"] == "original":
            shared["data"]["topics_hierarchy"] = exec_res["topics_hierarchy"]
            shared["data"]["sentiment_attributes"] = exec_res["sentiment_attributes"]
            shared["data"]["publisher_objects"] = exec_res["publisher_objects"]
            shared["data"]["belief_system"] = exec_res["belief_system"]
            print(f"[DataLoad] belief_system loaded: {len(exec_res['belief_system'])} items")

        if "stage1_results" not in shared:
            shared["stage1_results"] = {"statistics": {}}
        if "statistics" not in shared["stage1_results"]:
            shared["stage1_results"]["statistics"] = {
                "total_blogs": 0,
                "processed_blogs": 0,
                "empty_fields": {
                    "sentiment_polarity_empty": 0,
                    "sentiment_attribute_empty": 0,
                    "topics_empty": 0,
                    "publisher_empty": 0,
                    "belief_system_empty": 0,
                },
                "engagement_statistics": {
                    "total_reposts": 0,
                    "total_comments": 0,
                    "total_likes": 0,
                    "avg_reposts": 0.0,
                    "avg_comments": 0.0,
                    "avg_likes": 0.0,
                },
                "user_statistics": {
                    "unique_users": 0,
                    "top_active_users": [],
                    "user_type_distribution": {},
                },
                "content_statistics": {
                    "total_images": 0,
                    "blogs_with_images": 0,
                    "avg_content_length": 0.0,
                    "time_distribution": {},
                },
                "geographic_distribution": {},
            }

        shared["stage1_results"]["statistics"]["total_blogs"] = len(exec_res["blog_data"])

        print(f"[DataLoad] 加载完成，共 {len(exec_res['blog_data'])} 条博文")

        return "default"
