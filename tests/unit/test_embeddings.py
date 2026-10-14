"""Unit tests for embedding services and vector math."""
import math
import pytest
from app.services.llm.embeddings import (
    cosine_similarity,
    generate_deterministic_embedding,
    EMBEDDING_DIM,
)


def test_cosine_similarity_identical_vectors():
    vec = [1.0, 2.0, 3.0]
    sim = cosine_similarity(vec, vec)
    assert pytest.approx(sim, 0.0001) == 1.0


def test_cosine_similarity_orthogonal_vectors():
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [0.0, 1.0, 0.0]
    sim = cosine_similarity(vec_a, vec_b)
    assert pytest.approx(sim, 0.0001) == 0.0


def test_cosine_similarity_zero_vector():
    vec_a = [0.0, 0.0, 0.0]
    vec_b = [1.0, 2.0, 3.0]
    assert cosine_similarity(vec_a, vec_b) == 0.0


def test_generate_deterministic_embedding():
    text = "Electric charges and fields in physics"
    emb = generate_deterministic_embedding(text)
    assert len(emb) == EMBEDDING_DIM
    # Vector should be normalized (norm approx 1.0)
    norm = math.sqrt(sum(x * x for x in emb))
    assert pytest.approx(norm, 0.0001) == 1.0
