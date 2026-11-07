import importlib_metadata

try:
    version = importlib_metadata.version("litellm")
except Exception:
    version = "1.108.2"

if not version or version == "unknown":
    version = "1.108.2"
