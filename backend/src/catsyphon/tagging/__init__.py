"""Conversation tagging module for extracting metadata from parsed conversations."""

from .base import BaseTagger
from .cache import TagCache
from .job_queue import QueueStats, TaggingJobQueue
from .llm_tagger import LLMTagger
from .pipeline import TaggingPipeline
from .rule_tagger import RuleTagger
from .worker import TaggingWorker, get_worker_stats, start_worker, stop_worker

__all__ = [
    "BaseTagger",
    "TagCache",
    "LLMTagger",
    "RuleTagger",
    "TaggingPipeline",
    "TaggingJobQueue",
    "QueueStats",
    "TaggingWorker",
    "start_worker",
    "stop_worker",
    "get_worker_stats",
]
