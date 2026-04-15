import pickle
import os, platform
from collections import defaultdict
import attr
from pathlib import Path

p = Path.home() / ".messpy" / "messpy_config"


@attr.s(auto_attribs=True)
class Config:
    exp_settings: dict = attr.Factory(lambda: defaultdict(dict))
    conf_path: str = p
    data_directory: Path = Path("C:") / "results"
    testing = False
    last_results: dict = attr.Factory(dict)

    def save(self, fname=p):
        with open(fname, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, fname) -> "Config":
        with open(fname, "rb") as f:
            d = pickle.load(f)
            return d


config = Config()
config_available = os.path.exists(p)
if config_available:
    try:
        f = attr.asdict(Config.load(p))
        for key, val in f.items():
            setattr(config, key, val)
    except (EOFError, IOError, AttributeError):
        pass


config.data_directory = Path("C:/") / "results"
