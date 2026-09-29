"""Interpreta el reporte real. No convierte errores del escáner en éxitos."""
import json
from pathlib import Path

report = json.loads(Path("reports/zap.json").read_text(encoding="utf-8-sig"))
counts = {"high": 0, "medium": 0, "low": 0, "informational": 0}
labels = {"3": "high", "2": "medium", "1": "low", "0": "informational"}
for site in report.get("site", []):
    for alert in site.get("alerts", []):
        counts[labels[str(alert["riskcode"])]] += 1
Path("reports/zap-summary.json").write_text(json.dumps(counts, indent=2))
print(json.dumps(counts, indent=2))
raise SystemExit(1 if counts["high"] or counts["medium"] else 0)
