from pathlib import Path
import json

# Base directory for this module (preset.py)
BASE_DIR = Path(__file__).resolve().parent


# Directory where preset JSON files are stored
# Created automatically on module import
PRESET_DIR = BASE_DIR / "presets"
PRESET_DIR.mkdir(exist_ok=True)


def _safe_preset_name(name: str) -> str:
    """
    Validate and sanitize a preset name to avoid path manipulation issues.

    Rules:
    - Leading/trailing whitespace is stripped.
    - Empty names are not allowed.
    - Names cannot contain path separators ('/' or '\\'), which prevents
      directory traversal and other unsafe file system access.

    Raises:
        ValueError: If the name is empty or contains illegal characters.
    """
    name = name.strip()
    if not name or "/" in name or "\\" in name:
        raise ValueError("Invalid preset name")
    return name


def list_presets():
    """
    Return a sorted list of all available preset names.

    The returned names do NOT include the `.json` extension.
    """
    return sorted(p.stem for p in PRESET_DIR.glob("*.json"))


def save_preset(name: str, style: dict):
    """
    Save a preset dictionary to disk as `<name>.json`.

    Behavior:
    - Validates the preset name using `_safe_preset_name`.
    - Does not overwrite existing files; raises FileExistsError instead.
    - Writes the JSON file in UTF-8 with pretty indentation for readability.

    Args:
        name: The preset name (without `.json`).
        style: A dictionary containing all settings to store.

    Raises:
        FileExistsError: If a preset with the same name already exists.
        ValueError: If the preset name is invalid.
    """
    name = _safe_preset_name(name)
    path = PRESET_DIR / f"{name}.json"
    if path.exists():
        raise FileExistsError("Preset already exists")
    with path.open("w", encoding="utf-8") as f:
        json.dump(style, f, ensure_ascii=False, indent=2)


def load_preset(name: str) -> dict:
    """
    Load and return a preset dictionary by name.

    Format Compatibility:
    - Supports presets stored as:
        { ... }
        { "state": { ... } }
      The function automatically normalizes both to a plain state dictionary.

    Returns:
        The loaded preset dictionary, or None if the file does not exist.

    Raises:
        ValueError: If the preset name is invalid.
    """
    name = _safe_preset_name(name)
    path = PRESET_DIR / f"{name}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Normalize formats. If stored as {"state": {...}}, return only the inner dict.
    if "state" in data:
        return data["state"]
    return data


def delete_preset(name: str):
    """
    Delete a preset file if it exists.

    Behavior:
    - Validates the preset name.
    - Removes `<name>.json` if present.
    - Silently ignores deletion if the file does not exist (no exception raised).

    Raises:
        ValueError: If the preset name is invalid.
    """
    name = _safe_preset_name(name)
    path = PRESET_DIR / f"{name}.json"
    if path.exists():
        path.unlink()