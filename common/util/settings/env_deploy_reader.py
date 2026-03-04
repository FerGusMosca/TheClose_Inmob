# utils/env_deploy_reader.py
from pathlib import Path
import os, json

class EnvDeployReader:
    _config = {}
    _path = None
    _cache_file = Path("config/.env_deploy_cache.json")

    @classmethod
    def _find_file(cls, env_file: str):
        cwd = Path.cwd()
        for p in [cwd, *cwd.parents]:
            f = p / env_file
            if f.exists():
                return f
        here = Path(__file__).resolve()
        for p in [here.parent, *here.parents]:
            f = p / env_file
            if f.exists():
                return f
        return None

    @classmethod
    def load(cls, env_file: str):
        # 1) If the variable already exists in os.environ, skip file loading
        if env_file in os.environ:
            cls._config.clear()
            # Optionally cache all current environment variables
            cls._config.update(os.environ)
            return

        # 2) If not in os.environ, try to locate the file on disk
        path = cls._find_file(env_file)
        if not path:
            raise FileNotFoundError(f"Config '{env_file}' not found")

        cls._path = path
        cls._config.clear()

        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.split("#", 1)[0].strip()
                cls._config[k.strip()] = v

        # Persist config to cache
        cls._cache_file.write_text(json.dumps(cls._config), encoding="utf-8")

    @classmethod
    def get(cls, key: str, default=None):
        # if not loaded in memory, try load from cache
        if not cls._config and cls._cache_file.exists():
            cls._config = json.loads(cls._cache_file.read_text(encoding="utf-8"))

        if key in os.environ:
            return os.environ[key]
        if key in cls._config:
            return cls._config[key]
        if default is not None:
            return default
        raise KeyError(f"Missing config key '{key}' in {cls._path}")
