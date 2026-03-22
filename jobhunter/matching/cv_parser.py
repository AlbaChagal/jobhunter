"""CV loading and text extraction utilities."""

from __future__ import annotations

from pathlib import Path


def load_cv(cv: str | Path) -> str:
    """
    Load a CV and return its text content as a plain string.

    Supported inputs:
    - A plain string — returned as-is.
    - A ``Path`` (or string path) to a ``.pdf`` file — text extracted via ``pdfplumber``.
    - A ``Path`` (or string path) to any other text file — read as UTF-8.

    Args:
        cv: The CV as a string, or a path to a PDF/text file.

    Returns:
        The full CV text.

    Raises:
        FileNotFoundError: If the given path does not exist.
        ValueError: If the file type is not supported.
    """
    # If it's already a string but looks like a file path, try to treat it as one
    if isinstance(cv, str):
        candidate = Path(cv)
        if candidate.exists():
            return _load_file(candidate)
        # Otherwise treat the string itself as CV text
        return cv

    path = Path(cv)
    if not path.exists():
        raise FileNotFoundError(f"CV file not found: {path}")
    return _load_file(path)


def _load_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path)
    # Treat anything else as plain text
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _load_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "The 'pdfplumber' package is required to parse PDF CVs. "
            "Install it with: pip install pdfplumber"
        )

    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)

    if not pages:
        raise ValueError(f"Could not extract any text from PDF: {path}")

    return "\n\n".join(pages)
