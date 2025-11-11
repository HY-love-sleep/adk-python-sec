"""
Category Matcher using Embedding Similarity
"""

import time
from typing import Tuple, List
from .category_config import STANDARD_CATEGORIES, CATEGORY_ALIASES


class CategoryMatcher:
    """类别匹配器 - 使用 Embedding 相似度匹配"""
    
    def __init__(self, similarity_threshold: float = 0.7):
        """
        Args:
            similarity_threshold: 相似度阈值，低于此值将回退为原始类别
        """
        self.similarity_threshold = similarity_threshold
        self.client = None  # 延迟初始化
        self._category_embeddings_cache = {}
    
    def _get_client(self):
        """延迟初始化 Google Generative AI Client"""
        if self.client is None:
            from google import genai
            self.client = genai.Client()
        return self.client
    
    async def find_best_match(self, user_category: str) -> Tuple[str, float, str]:
        """
        找到最匹配的标准类别
        
        Args:
            user_category: 用户输入的类别名
            
        Returns:
            (matched_category, similarity_score, status)
            - matched_category: 匹配到的标准类别（或原始类别）
            - similarity_score: 相似度分数 (0-1)
            - status: 'matched' | 'original' | 'alias' | 'unmatched'
            
        Logic:
            1. 别名映射（返回标准类别）
            2. 精确匹配（返回标准类别）
            3. Embedding 相似度匹配（高于阈值返回标准类别，否则返回原始输入）
        """
        if not user_category or not user_category.strip():
            return "其他", 0.0, "default"
        
        user_category = user_category.strip()
        
        # 检查是否在别名映射中
        if user_category in CATEGORY_ALIASES:
            matched = CATEGORY_ALIASES[user_category]
            return matched, 1.0, "alias"
        
        # 精确匹配
        if user_category in STANDARD_CATEGORIES:
            return user_category, 1.0, "matched"
        
        # 使用 embedding 相似度匹配
        try:
            matched_category, similarity = await self._embedding_match(user_category)
            
            # 根据相似度决定是否使用匹配结果
            if similarity >= self.similarity_threshold:
                return matched_category, similarity, "matched"
            else:
                return user_category, similarity, "unmatched"
        
        except Exception as e:
            # Embedding 匹配失败，返回原始输入
            print(f" Embedding match failed: {e}, using original category: {user_category}")
            return user_category, 0.0, "error"
    
    async def _embedding_match(self, user_category: str) -> Tuple[str, float]:
        """
        使用 Embedding 计算相似度
        
        Returns:
            (matched_category, similarity_score)
        """
        try:
            from google import genai
            import asyncio
            
            # 使用同步 API（暂时，避免复杂的异步问题）
            client = genai.Client()
            from numpy import dot, asarray
            from numpy.linalg import norm
            
            # 获取用户输入的 embedding
            user_emb_response = client.models.embed_content(
                model="models/embedding-001",
                contents=[{"parts": [{"text": user_category}]}]
            )
            user_embedding = asarray(user_emb_response.embeddings[0].values)
            
            # 计算与所有标准类别的相似度
            max_similarity = -1
            best_match = STANDARD_CATEGORIES[0]
            
            for standard_cat in STANDARD_CATEGORIES:
                try:
                    std_emb_response = client.models.embed_content(
                        model="models/embedding-001",
                        contents=[{"parts": [{"text": standard_cat}]}]
                    )
                    std_embedding = asarray(std_emb_response.embeddings[0].values)
                    
                    # 计算余弦相似度
                    similarity = dot(user_embedding, std_embedding) / (
                        norm(user_embedding) * norm(std_embedding)
                    )
                    
                    if similarity > max_similarity:
                        max_similarity = similarity
                        best_match = standard_cat
                        
                except Exception as e:
                    print(f"⚠️ Failed to get embedding for '{standard_cat}': {e}")
                    continue
            
            return best_match, float(max_similarity)
            
        except Exception as e:
            print(f"⚠️ Embedding match failed: {e}")
            # 返回默认值
            return STANDARD_CATEGORIES[0], 0.0
    
    async def batch_match(self, user_categories: List[str]) -> List[Tuple[str, str, float, str]]:
        """
        批量匹配多个类别
        
        Args:
            user_categories: 用户输入的类别名列表
            
        Returns:
            List[(original, matched, similarity, status)]
        """
        results = []
        for category in user_categories:
            matched, similarity, status = await self.find_best_match(category)
            results.append((category, matched, similarity, status))
        return results


# 创建全局实例
category_matcher = CategoryMatcher(similarity_threshold=0.7)

