import pytest

from src.retriever import IndexNotFoundError, Retriever, distance_to_similarity, reciprocal_rank_fusion
from tests.conftest import FakeCollection, fake_embed


def test_distance_to_similarity_matches_chroma_cosine():
    assert distance_to_similarity(0.0) == 1.0
    assert distance_to_similarity(1.0) == 0.0
    assert distance_to_similarity(2.0) == -1.0


def test_rrf_rewards_items_ranked_by_both_lists():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "x", "y"]])
    assert fused[0] == "b"
    assert set(fused) == {"a", "b", "c", "x", "y"}


def test_relevant_chunk_ranks_first(retriever):
    results = retriever.retrieve("when should I use kafka", top_k=3)
    assert results[0].source == "messaging.md"
    assert results[0].section == "Messaging > Kafka"
    assert results[0].score > 0.3


def test_off_topic_question_returns_nothing(retriever):
    assert retriever.retrieve("best pizza recipe") == []


def test_keyword_match_is_fused_in(retriever):
    results = retriever.retrieve("2pc or saga?", top_k=2)
    assert results[0].section == "Consistency > 2PC"


def test_top_k_is_respected(retriever):
    assert len(retriever.retrieve("kafka rabbitmq queue cache redis", top_k=2)) == 2


def test_empty_index_raises():
    with pytest.raises(IndexNotFoundError):
        Retriever(collection=FakeCollection({}), embed=fake_embed)


def test_sources_and_count(retriever):
    assert retriever.doc_count() == 5
    assert retriever.list_sources() == ["caching.md", "consistency.md", "database.md", "messaging.md"]


async def test_aretrieve_runs_off_loop(retriever):
    results = await retriever.aretrieve("redis cache", top_k=1)
    assert results[0].source == "caching.md"
