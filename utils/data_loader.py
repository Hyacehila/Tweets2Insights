import json
import os
import tempfile
from typing import List, Dict, Any
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_blog_data(data_file_path: str) -> List[Dict[str, Any]]:
    """
    加载博文数据
    
    Args:
        data_file_path: 博文数据文件路径
        
    Returns:
        List[Dict[str, Any]]: 博文数据列表
    """
    try:
        with open(data_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"成功加载博文数据，共 {len(data)} 条记录")
        return data
        
    except Exception as e:
        logger.error(f"加载博文数据失败: {e}")
        raise

def load_topics(topics_file_path: str) -> List[Dict[str, Any]]:
    """
    加载主题数据
    
    Args:
        topics_file_path: 主题数据文件路径
        
    Returns:
        List[Dict[str, Any]]: 主题数据列表，每个元素包含parent_topic和sub_topics
    """
    try:
        with open(topics_file_path, 'r', encoding='utf-8') as f:
            topics = json.load(f)
        
        logger.info(f"成功加载主题数据，共 {len(topics)} 个父主题")
        return topics
        
    except Exception as e:
        logger.error(f"加载主题数据失败: {e}")
        raise

def load_sentiment_attributes(sentiment_attributes_file_path: str) -> List[str]:
    """
    加载情感属性数据
    
    Args:
        sentiment_attributes_file_path: 情感属性文件路径
        
    Returns:
        List[str]: 情感属性列表
    """
    try:
        with open(sentiment_attributes_file_path, 'r', encoding='utf-8') as f:
            attributes = json.load(f)
        
        logger.info(f"成功加载情感属性数据，共 {len(attributes)} 个")
        return attributes
        
    except Exception as e:
        logger.error(f"加载情感属性数据失败: {e}")
        raise

def load_publisher_objects(publisher_objects_file_path: str) -> List[str]:
    """
    加载发布者对象数据
    
    Args:
        publisher_objects_file_path: 发布者对象文件路径
        
    Returns:
        List[str]: 发布者对象列表
    """
    try:
        with open(publisher_objects_file_path, 'r', encoding='utf-8') as f:
            objects = json.load(f)
        
        logger.info(f"成功加载发布者对象数据，共 {len(objects)} 个")
        return objects
        
    except Exception as e:
        logger.error(f"加载发布者对象数据失败: {e}")
        raise


def load_belief_system(belief_system_file_path: str) -> List[Dict[str, Any]]:
    """
    加载通用信念体系分类（category/subcategories）
    """
    try:
        with open(belief_system_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"成功加载信念体系分类，共 {len(data)} 条")
        return data
    except Exception as e:
        logger.error(f"加载信念体系失败: {e}")
        raise


def save_enhanced_blog_data(enhanced_blog_data: List[Dict[str, Any]], output_path: str) -> bool:
    """
    保存增强后的博文数据
    
    Args:
        enhanced_blog_data: 增强后的博文数据
        output_path: 输出文件路径
        
    Returns:
        bool: 保存是否成功
    """
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=".tmp_enhanced_",
            suffix=".json",
            dir=output_dir or None
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(enhanced_blog_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, output_path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

        logger.info(f"成功保存增强博文数据到 {output_path}，共 {len(enhanced_blog_data)} 条记录")
        return True
    except Exception as e:
        logger.error(f"保存增强博文数据失败: {e}")
        return False

def load_enhanced_blog_data(enhanced_data_path: str) -> List[Dict[str, Any]]:
    """
    加载增强后的博文数据
    
    Args:
        enhanced_data_path: 增强数据文件路径
        
    Returns:
        List[Dict[str, Any]]: 增强博文数据列表
    """
    try:
        with open(enhanced_data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"成功加载增强博文数据，共 {len(data)} 条记录")
        return data
        
    except Exception as e:
        logger.error(f"加载增强博文数据失败: {e}")
        raise


def save_analysis_results(results: Dict[str, Any], output_path: str) -> bool:
    """
    保存分析结果
    
    Args:
        results: 分析结果字典
        output_path: 输出文件路径
        
    Returns:
        bool: 保存是否成功
    """
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"成功保存分析结果到 {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"保存分析结果失败: {e}")
        return False


def load_analysis_results(results_path: str) -> Dict[str, Any]:
    """
    加载分析结果
    
    Args:
        results_path: 分析结果文件路径
        
    Returns:
        Dict[str, Any]: 分析结果字典
    """
    try:
        with open(results_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"成功加载分析结果: {results_path}")
        return data
        
    except Exception as e:
        logger.error(f"加载分析结果失败: {e}")
        raise


def check_stage_output_exists(stage: int) -> Dict[str, bool]:
    """
    检查指定阶段的输出文件是否存在
    
    Args:
        stage: 阶段编号 (1, 2, 3)
        
    Returns:
        Dict[str, bool]: 各输出文件的存在状态
    """
    if stage == 1:
        return {
            "enhanced_posts": os.path.exists("data/enhanced_blogs.json")
        }
    elif stage == 2:
        return {
            "analysis_data": os.path.exists("report/analysis_data.json"),
            "insights": os.path.exists("report/insights.json"),
            "images_dir": os.path.exists("report/images")
        }
    elif stage == 3:
        return {
            "report": os.path.exists("report/report.md")
        }
    else:
        return {}


def get_sample_posts(blog_data: List[Dict[str, Any]], 
                     sample_size: int = 10,
                     strategy: str = "random") -> List[Dict[str, Any]]:
    """
    从博文数据中抽取样本
    
    Args:
        blog_data: 博文数据列表
        sample_size: 样本数量
        strategy: 抽样策略 - "random"随机, "influential"高影响力, "diverse"多样性
        
    Returns:
        List[Dict[str, Any]]: 样本博文列表
    """
    import random
    
    if not blog_data:
        return []
    
    if len(blog_data) <= sample_size:
        return blog_data
    
    if strategy == "random":
        return random.sample(blog_data, sample_size)
    
    elif strategy == "influential":
        # 按影响力排序（转发+评论+点赞）
        sorted_posts = sorted(
            blog_data,
            key=lambda x: (
                x.get("repost_count", 0) + 
                x.get("comment_count", 0) + 
                x.get("like_count", 0)
            ),
            reverse=True
        )
        return sorted_posts[:sample_size]
    
    elif strategy == "diverse":
        # 尝试覆盖不同情感和主题
        samples = []
        sentiment_buckets = {1: [], 2: [], 3: [], 4: [], 5: []}
        
        for post in blog_data:
            polarity = post.get("sentiment_polarity", 3)
            if polarity in sentiment_buckets:
                sentiment_buckets[polarity].append(post)
        
        # 从每个情感桶中均匀抽取
        per_bucket = max(1, sample_size // 5)
        for polarity, posts in sentiment_buckets.items():
            if posts:
                samples.extend(random.sample(posts, min(per_bucket, len(posts))))
        
        # 如果不够，随机补充
        if len(samples) < sample_size:
            remaining = [p for p in blog_data if p not in samples]
            additional = random.sample(remaining, min(sample_size - len(samples), len(remaining)))
            samples.extend(additional)
        
        return samples[:sample_size]
    
    return random.sample(blog_data, sample_size)
