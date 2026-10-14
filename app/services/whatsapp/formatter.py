"""WhatsApp message formatter, LaTeX converter, and 4096-char chunker."""
import re
from typing import List

MAX_WHATSAPP_TEXT_LENGTH = 4096


def clean_latex_for_whatsapp(text: str) -> str:
    """
    Converts common LaTeX expressions into clean Unicode and plain text notations
    suitable for WhatsApp readability.
    """
    if not text:
        return ""

    replacements = [
        (r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1/\2)"),
        (r"\\sqrt\{([^{}]+)\}", r"√(\1)"),
        (r"\\times", "×"),
        (r"\\div", "÷"),
        (r"\\pm", "±"),
        (r"\\approx", "≈"),
        (r"\\neq", "≠"),
        (r"\\leq", "≤"),
        (r"\\geq", "≥"),
        (r"\\infty", "∞"),
        (r"\\pi", "π"),
        (r"\\theta", "θ"),
        (r"\\alpha", "α"),
        (r"\\beta", "β"),
        (r"\\Delta", "Δ"),
        (r"\\rightarrow", "→"),
        (r"\^2", "²"),
        (r"\^3", "³"),
        (r"\^0", "⁰"),
        (r"\^1", "¹"),
        (r"\_0", "₀"),
        (r"\_1", "₁"),
        (r"\_2", "₂"),
        (r"\_n", "ₙ"),
    ]

    result = text
    for pattern, repl in replacements:
        result = re.sub(pattern, repl, result)

    # Remove display math $$...$$ and inline math $...$ delimiters
    result = re.sub(r"\$\$([^\$]+)\$\$", r"\1", result)
    result = re.sub(r"\$([^\$]+)\$", r"\1", result)

    # Clean double backslashes
    result = re.sub(r"\\\\", "\n", result)
    return result


def split_message_for_whatsapp(
    text: str, max_length: int = MAX_WHATSAPP_TEXT_LENGTH
) -> List[str]:
    """
    Splits long messages exceeding max_length into smaller chunks along
    natural paragraph, sentence, or word boundaries.

    Args:
        text: The text to split.
        max_length: Maximum allowed characters per chunk (default 4096).

    Returns:
        List[str]: List of text chunks, each <= max_length characters.
    """
    if not text or len(text) <= max_length:
        return [text] if text else []

    chunks: List[str] = []
    remaining = text.strip()

    while len(remaining) > max_length:
        # Search for safe splitting point before max_length
        split_idx = -1

        # 1. Try double newline (paragraph boundary)
        p_idx = remaining.rfind("\n\n", 0, max_length)
        if p_idx != -1 and p_idx > max_length // 2:
            split_idx = p_idx + 2

        # 2. Try single newline
        if split_idx == -1:
            n_idx = remaining.rfind("\n", 0, max_length)
            if n_idx != -1 and n_idx > max_length // 2:
                split_idx = n_idx + 1

        # 3. Try sentence end (. ! ? followed by space or newline)
        if split_idx == -1:
            for punct in [". ", "! ", "? "]:
                s_idx = remaining.rfind(punct, 0, max_length)
                if s_idx != -1 and s_idx > max_length // 2:
                    split_idx = s_idx + len(punct)
                    break

        # 4. Fallback: try space
        if split_idx == -1:
            sp_idx = remaining.rfind(" ", 0, max_length)
            if sp_idx != -1 and sp_idx > max_length // 4:
                split_idx = sp_idx + 1

        # 5. Last resort: hard split at max_length
        if split_idx == -1:
            split_idx = max_length

        chunk = remaining[:split_idx].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_idx:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks
