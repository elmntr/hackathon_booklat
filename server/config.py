"""Project configuration, independent of the launch directory."""
from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Read configuration once per process."""
    with Path(__file__).with_name("config.yaml").open(encoding="utf-8") as source:
        return yaml.safe_load(source)
