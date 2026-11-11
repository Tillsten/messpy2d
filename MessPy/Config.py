import json
from pathlib import Path

import attr
import cattrs
from loguru import logger

CONFIG_PATH = Path.home() / ".messpy" / "messpy_config.json"

# JSON (not TOML) because exp_settings/last_results are arbitrary
# pyqtgraph Parameter.saveState() blobs that may contain None, which
# TOML cannot represent.
converter = cattrs.Converter()
converter.register_structure_hook(Path, lambda v, _: Path(v))
converter.register_unstructure_hook(Path, str)


@attr.s(auto_attribs=True)
class Config:
    exp_settings: dict = attr.Factory(dict)
    data_directory: Path = Path("C:") / "results"
    testing: bool = False
    last_results: dict = attr.Factory(dict)
    shots: int = 20

    def save(self, path: Path = CONFIG_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(converter.unstructure(self), indent=2))

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        data = json.loads(path.read_text())
        return converter.structure(data, cls)


config = Config()
if CONFIG_PATH.exists():
    try:
        config = Config.load()
    except (OSError, json.JSONDecodeError, cattrs.ClassValidationError) as e:
        logger.warning(f"Could not load config from {CONFIG_PATH}: {e}")
