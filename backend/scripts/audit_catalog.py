import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))

from app.services.item_catalog import ItemCatalog  # noqa: E402


def main() -> int:
    catalog = ItemCatalog(BACKEND_DIR / "app" / "data" / "items")
    report = catalog.quality_report()
    print(json.dumps(report.model_dump(), indent=2))
    return 1 if report.alias_conflicts else 0


if __name__ == "__main__":
    raise SystemExit(main())
