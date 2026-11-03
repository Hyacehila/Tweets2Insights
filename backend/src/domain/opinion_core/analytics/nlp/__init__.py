"""
Lightweight NLP utilities (tokenization, keywords, NER, similarity).
"""
from opinion_core.analytics.nlp.text_cleaner import clean_text
from opinion_core.analytics.nlp.tokenizer import tokenize, tokenize_batch
from opinion_core.analytics.nlp.keyword_extractor import extract_keywords, extract_keywords_batch
from opinion_core.analytics.nlp.ner import extract_entities
from opinion_core.analytics.nlp.sentiment_lexicon import lexicon_sentiment
from opinion_core.analytics.nlp.similarity import cluster_similar_texts

__all__ = [
    "clean_text",
    "tokenize",
    "tokenize_batch",
    "extract_keywords",
    "extract_keywords_batch",
    "extract_entities",
    "lexicon_sentiment",
    "cluster_similar_texts",
]
