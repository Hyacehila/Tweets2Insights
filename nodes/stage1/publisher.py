"""
Stage 1 publisher analysis nodes.
"""
import asyncio
from typing import Any

from nodes.base import AsyncParallelBatchNode
from utils.call_llm import call_glm_45_air


class AsyncPublisherObjectAnalysisBatchNode(AsyncParallelBatchNode):
    """
    异步发布者对象分析节点
    """

    def apply_item_result(self, item: Any, result: Any) -> None:
        if isinstance(item, dict) and isinstance(item.get("blog_data"), dict):
            item["blog_data"]["publisher"] = result

    async def prep_async(self, shared):
        blog_data = shared.get("data", {}).get("blog_data", [])
        publisher_objects = shared.get("data", {}).get("publisher_objects", [])

        self._configure_checkpoint(shared, blog_data)

        return [
            {"blog_data": blog_post, "publisher_objects": publisher_objects}
            for blog_post in blog_data
        ]

    async def exec_async(self, prep_res):
        blog_post = prep_res["blog_data"]
        publisher_objects = prep_res["publisher_objects"]
        existing = blog_post.get("publisher")
        if existing is not None:
            return existing

        publishers_str = "、".join(publisher_objects)
        username = blog_post.get("username", "") or blog_post.get("user_name", "")
        extra_user = f"\n发布者昵称/账号：{username}" if username else ""

        prompt = f"""候选发布者：{publishers_str}
判断该博文最可能的发布者类型，直接输出候选列表中的一个条目，不得添加解释。
博文：
{blog_post.get('content', '')}{extra_user}"""

        response = await asyncio.to_thread(call_glm_45_air, prompt, temperature=0.3)
        publisher = response.strip()

        if publisher in publisher_objects:
            return publisher
        return "个人用户" if "个人用户" in publisher_objects else None

    async def exec_fallback_async(self, prep_res, exc):
        print(f"发布者分析失败，使用默认值: {str(exc)}")
        return "个人用户"

    async def post_async(self, shared, prep_res, exec_res):
        blog_data = shared.get("data", {}).get("blog_data", [])
        if len(exec_res) != len(blog_data):
            print("警告：发布者分析结果数量与博文数量不匹配")
            return "default"

        for i, blog_post in enumerate(blog_data):
            blog_post["publisher"] = exec_res[i] if i < len(exec_res) else None

        print(f"[AsyncPublisher] 完成 {len(exec_res)} 条博文的发布者分析")
        return "default"
