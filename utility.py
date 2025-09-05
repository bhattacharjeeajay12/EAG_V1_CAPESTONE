import json
import os
from typing import Any, Optional


def load_json(file_path: str) -> dict:
    """
    Load and parse a JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON content as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        JSONDecodeError: If file contains invalid JSON
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"JSON file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_json_safe(file_path: str, default: Optional[Any] = None) -> Any:
    """
    Safely load and parse a JSON file with fallback to default value.

    Args:
        file_path: Path to the JSON file
        default: Default value to return if loading fails

    Returns:
        Parsed JSON content or default value if loading fails
    """
    try:
        return load_json(file_path)
    except (FileNotFoundError, json.JSONDecodeError):
        return default
