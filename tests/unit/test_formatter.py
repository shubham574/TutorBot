"""Unit tests for WhatsApp formatting and 4096-char chunker."""
import pytest
from app.services.whatsapp.formatter import (
    clean_latex_for_whatsapp,
    split_message_for_whatsapp,
    MAX_WHATSAPP_TEXT_LENGTH,
)


def test_clean_latex_fractions_and_roots():
    latex = r"The derivative is \frac{dy}{dx} and \sqrt{16} = 4"
    cleaned = clean_latex_for_whatsapp(latex)
    assert cleaned == "The derivative is (dy/dx) and √(16) = 4"


def test_clean_latex_math_delimiters():
    latex = r"Recall that $E = mc^2$ and $$\int x dx = \frac{x^2}{2}$$."
    cleaned = clean_latex_for_whatsapp(latex)
    assert "$$" not in cleaned
    assert "$" not in cleaned
    assert "E = mc²" in cleaned
    assert "(x²/2)" in cleaned


def test_clean_latex_symbols():
    latex = r"a \times b \approx c \pm d"
    cleaned = clean_latex_for_whatsapp(latex)
    assert "a × b ≈ c ± d" == cleaned


def test_split_short_message():
    text = "Hello student, welcome to TutorBot!"
    chunks = split_message_for_whatsapp(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_exact_max_length():
    text = "A" * MAX_WHATSAPP_TEXT_LENGTH
    chunks = split_message_for_whatsapp(text)
    assert len(chunks) == 1
    assert len(chunks[0]) == MAX_WHATSAPP_TEXT_LENGTH


def test_split_paragraphs_boundary():
    # Create two paragraphs, each 2500 characters
    p1 = "Paragraph one starts here. " + ("A" * 2400) + "\n\n"
    p2 = "Paragraph two starts here. " + ("B" * 2400)
    full_text = p1 + p2
    assert len(full_text) > MAX_WHATSAPP_TEXT_LENGTH

    chunks = split_message_for_whatsapp(full_text)
    assert len(chunks) == 2
    assert all(len(c) <= MAX_WHATSAPP_TEXT_LENGTH for c in chunks)
    assert chunks[0].startswith("Paragraph one")
    assert chunks[1].startswith("Paragraph two")


def test_split_sentences_boundary():
    s1 = "Sentence number one is fairly long. " * 80  # ~2880 chars
    s2 = "Sentence number two is also quite long. " * 60 # ~2340 chars
    full_text = s1 + s2
    assert len(full_text) > MAX_WHATSAPP_TEXT_LENGTH

    chunks = split_message_for_whatsapp(full_text)
    assert len(chunks) >= 2
    assert all(len(c) <= MAX_WHATSAPP_TEXT_LENGTH for c in chunks)


def test_split_unbroken_long_string():
    long_string = "X" * (MAX_WHATSAPP_TEXT_LENGTH + 500)
    chunks = split_message_for_whatsapp(long_string)
    assert len(chunks) == 2
    assert len(chunks[0]) == MAX_WHATSAPP_TEXT_LENGTH
    assert len(chunks[1]) == 500
