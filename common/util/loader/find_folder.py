from pathlib import Path


class FindFolder():

    @staticmethod
    def find_config_dir(start: Path) -> Path:
        for p in [start, *start.parents]:
            cand = p / "config"
            if cand.exists():
                return cand
        return start / "config"