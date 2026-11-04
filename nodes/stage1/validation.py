"""
Stage 1 validation and overview node.
"""
from nodes.base import MonitoredNode


class DataValidationAndOverviewNode(MonitoredNode):
    """
    数据验证与概况分析节点
    """

    def prep(self, shared):
        return shared.get("data", {}).get("blog_data", [])

    def exec(self, prep_res):
        blog_data = prep_res

        stats = {
            "total_blogs": len(blog_data),
            "processed_blogs": 0,
            "engagement_statistics": {
                "total_reposts": 0,
                "total_comments": 0,
                "total_likes": 0,
                "avg_reposts": 0,
                "avg_comments": 0,
                "avg_likes": 0,
            },
            "user_statistics": {
                "unique_users": set(),
                "top_active_users": [],
                "user_type_distribution": {},
            },
            "content_statistics": {
                "total_images": 0,
                "blogs_with_images": 0,
                "avg_content_length": 0,
                "time_distribution": {},
            },
            "geographic_distribution": {},
            "empty_fields": {
                "sentiment_polarity_empty": 0,
                "sentiment_attribute_empty": 0,
                "topics_empty": 0,
                "publisher_empty": 0,
                "belief_system_empty": 0,
            },
        }

        total_content_length = 0
        user_engagement = {}

        for blog_post in blog_data:
            has_analysis = (
                blog_post.get("sentiment_polarity") is not None
                or blog_post.get("sentiment_attribute") is not None
                or blog_post.get("topics") is not None
                or blog_post.get("publisher") is not None
            )
            if has_analysis:
                stats["processed_blogs"] += 1

            repost_count = blog_post.get("repost_count", 0)
            comment_count = blog_post.get("comment_count", 0)
            like_count = blog_post.get("like_count", 0)

            stats["engagement_statistics"]["total_reposts"] += repost_count
            stats["engagement_statistics"]["total_comments"] += comment_count
            stats["engagement_statistics"]["total_likes"] += like_count

            user_id = blog_post.get("user_id", "")
            username = blog_post.get("username", "")
            if user_id:
                stats["user_statistics"]["unique_users"].add(user_id)
                if user_id not in user_engagement:
                    user_engagement[user_id] = {"username": username, "total_engagement": 0}
                user_engagement[user_id]["total_engagement"] += repost_count + comment_count + like_count

            content = blog_post.get("content", "")
            total_content_length += len(content)

            image_urls = blog_post.get("image_urls", [])
            if image_urls:
                stats["content_statistics"]["total_images"] += len(image_urls)
                stats["content_statistics"]["blogs_with_images"] += 1

            publish_time = blog_post.get("publish_time", "")
            if publish_time:
                try:
                    hour = int(publish_time.split(" ")[1].split(":")[0]) if " " in publish_time else 0
                    hour_key = f"{hour:02d}:00"
                    stats["content_statistics"]["time_distribution"][hour_key] = (
                        stats["content_statistics"]["time_distribution"].get(hour_key, 0) + 1
                    )
                except Exception:
                    pass

            location = blog_post.get("location", "")
            if location:
                stats["geographic_distribution"][location] = (
                    stats["geographic_distribution"].get(location, 0) + 1
                )

            if blog_post.get("sentiment_polarity") is None:
                stats["empty_fields"]["sentiment_polarity_empty"] += 1
            if blog_post.get("sentiment_attribute") is None:
                stats["empty_fields"]["sentiment_attribute_empty"] += 1
            if blog_post.get("topics") is None:
                stats["empty_fields"]["topics_empty"] += 1
            if blog_post.get("publisher") is None:
                stats["empty_fields"]["publisher_empty"] += 1
            belief_signals = blog_post.get("belief_signals")
            if not belief_signals:
                stats["empty_fields"]["belief_system_empty"] += 1

            publisher = blog_post.get("publisher")
            if publisher:
                stats["user_statistics"]["user_type_distribution"][publisher] = (
                    stats["user_statistics"]["user_type_distribution"].get(publisher, 0) + 1
                )

        if stats["total_blogs"] > 0:
            stats["engagement_statistics"]["avg_reposts"] = (
                stats["engagement_statistics"]["total_reposts"] / stats["total_blogs"]
            )
            stats["engagement_statistics"]["avg_comments"] = (
                stats["engagement_statistics"]["total_comments"] / stats["total_blogs"]
            )
            stats["engagement_statistics"]["avg_likes"] = (
                stats["engagement_statistics"]["total_likes"] / stats["total_blogs"]
            )
            stats["content_statistics"]["avg_content_length"] = (
                total_content_length / stats["total_blogs"]
            )

        stats["user_statistics"]["unique_users"] = len(stats["user_statistics"]["unique_users"])

        sorted_users = sorted(
            user_engagement.items(),
            key=lambda x: x[1]["total_engagement"],
            reverse=True,
        )[:10]
        stats["user_statistics"]["top_active_users"] = [
            {"user_id": uid, "username": info["username"], "total_engagement": info["total_engagement"]}
            for uid, info in sorted_users
        ]

        return stats

    def post(self, shared, prep_res, exec_res):
        if "stage1_results" not in shared:
            shared["stage1_results"] = {}
        if "statistics" not in shared["stage1_results"]:
            shared["stage1_results"]["statistics"] = {}

        shared["stage1_results"]["statistics"].update(exec_res)

        stats = exec_res
        print("\n" + "=" * 60)
        print("阶段1 数据增强统计报告".center(52))
        print("=" * 60)

        print(f"\n[CHART] 基础统计:")
        print(f"  ├─ 总博文数: {stats.get('total_blogs', 0)}")
        print(f"  └─ 已处理数: {stats.get('processed_blogs', 0)}")

        empty_fields = stats.get("empty_fields", {})
        if empty_fields:
            print(f"\n[注意] 增强字段空值统计:")
            print(f"  ├─ 情感极性为空: {empty_fields.get('sentiment_polarity_empty', 0)}")
            print(f"  ├─ 情感属性为空: {empty_fields.get('sentiment_attribute_empty', 0)}")
            print(f"  ├─ 主题为空: {empty_fields.get('topics_empty', 0)}")
            print(f"  ├─ 发布者为空: {empty_fields.get('publisher_empty', 0)}")
            print(f"  ├─ 信念分类为空: {empty_fields.get('belief_system_empty', 0)}")

        engagement = stats.get("engagement_statistics", {})
        if engagement:
            print(f"\n[CHAT] 参与度统计:")
            print(f"  ├─ 总转发数: {engagement.get('total_reposts', 0)}")
            print(f"  ├─ 总评论数: {engagement.get('total_comments', 0)}")
            print(f"  ├─ 总点赞数: {engagement.get('total_likes', 0)}")
            print(f"  ├─ 平均转发: {engagement.get('avg_reposts', 0):.2f}")
            print(f"  ├─ 平均评论: {engagement.get('avg_comments', 0):.2f}")
            print(f"  └─ 平均点赞: {engagement.get('avg_likes', 0):.2f}")

        user_stats = stats.get("user_statistics", {})
        if user_stats:
            print(f"\n[USERS] 用户统计:")
            print(f"  ├─ 独立用户数: {user_stats.get('unique_users', 0)}")
            user_type_dist = user_stats.get("user_type_distribution", {})
            if user_type_dist:
                print(f"  └─ 发布者类型分布:")
                for i, (pub_type, count) in enumerate(sorted(user_type_dist.items(), key=lambda x: -x[1])):
                    prefix = "      ├─" if i < len(user_type_dist) - 1 else "      └─"
                    print(f"{prefix} {pub_type}: {count}")

        content_stats = stats.get("content_statistics", {})
        if content_stats:
            print(f"\n[CONTENT] 内容统计:")
            print(f"  ├─ 含图博文数: {content_stats.get('blogs_with_images', 0)}")
            print(f"  ├─ 总图片数: {content_stats.get('total_images', 0)}")
            print(f"  └─ 平均内容长度: {content_stats.get('avg_content_length', 0):.1f} 字符")

        geo_dist = stats.get("geographic_distribution", {})
        if geo_dist:
            print(f"\n[MAP] 地理分布 (Top 5):")
            sorted_geo = sorted(geo_dist.items(), key=lambda x: -x[1])[:5]
            for i, (location, count) in enumerate(sorted_geo):
                prefix = "  ├─" if i < len(sorted_geo) - 1 else "  └─"
                print(f"{prefix} {location}: {count}")

        print("\n" + "=" * 60 + "\n")
        return "default"
