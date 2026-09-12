"""Compares a new build against the last promoted one and writes a changelog entry.

This is the "improvement loop" bookkeeping: every successful run records what
actually changed (coverage, gainers/losers, market breadth, per-product
signals), so drift and improvements are visible over time instead of the
dashboard silently overwriting itself run after run.
"""
import json
from datetime import datetime, timezone
from pathlib import Path


def _signals_map(dataset: dict) -> dict:
    return {p["id"]: p.get("forecast", {}).get("signal") for p in dataset.get("products", [])}


def diff_summary(prev: dict | None, curr: dict) -> list[str]:
    lines = []
    cm, pm = curr.get("meta", {}), (prev or {}).get("meta", {})

    if not prev:
        lines.append(f"Primera corrida registrada: {cm.get('n_products')} productos, "
                      f"cobertura {cm.get('start_date')} → {cm.get('max_date')}.")
        return lines

    if cm.get("max_date") != pm.get("max_date"):
        lines.append(f"Nueva fecha de corte de datos: {pm.get('max_date')} → {cm.get('max_date')}.")
    if cm.get("n_products") != pm.get("n_products"):
        lines.append(f"Productos con historial completo: {pm.get('n_products')} → {cm.get('n_products')}.")

    cb = curr.get("insights", {}).get("market_breadth", {})
    pb = (prev or {}).get("insights", {}).get("market_breadth", {})
    if cb.get("avg_chg_1y") != pb.get("avg_chg_1y"):
        lines.append(f"Variación promedio de la canasta (52 sem): {pb.get('avg_chg_1y')}% → {cb.get('avg_chg_1y')}%.")
    if (cb.get("up"), cb.get("down")) != (pb.get("up"), pb.get("down")):
        lines.append(f"Amplitud de mercado: {pb.get('up')} suben / {pb.get('down')} bajan → "
                      f"{cb.get('up')} suben / {cb.get('down')} bajan.")

    cg = [p["id"] for p in curr.get("insights", {}).get("top_gainers", [])]
    pg = [p["id"] for p in (prev or {}).get("insights", {}).get("top_gainers", [])]
    if cg != pg:
        lines.append(f"Top ganadores cambió: {pg} → {cg}.")
    cl = [p["id"] for p in curr.get("insights", {}).get("top_losers", [])]
    pl = [p["id"] for p in (prev or {}).get("insights", {}).get("top_losers", [])]
    if cl != pl:
        lines.append(f"Top perdedores cambió: {pl} → {cl}.")

    curr_sig, prev_sig = _signals_map(curr), _signals_map(prev or {})
    flipped = [pid for pid in curr_sig if pid in prev_sig and curr_sig[pid] != prev_sig[pid]]
    if flipped:
        detail = ", ".join(f"{pid}: {prev_sig[pid]}→{curr_sig[pid]}" for pid in flipped[:10])
        lines.append(f"Señal de pronóstico cambió en {len(flipped)} producto(s): {detail}"
                      + (" ..." if len(flipped) > 10 else ""))

    if not lines:
        lines.append("Sin cambios materiales respecto a la corrida anterior (misma fecha de datos).")
    return lines


def write_entry(changelog_path: Path, summary_lines: list[str], status: str, issues: list[str] | None = None):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = [f"## {ts} — {status}"]
    block += [f"- {line}" for line in summary_lines]
    if issues:
        block.append("- **Problemas detectados (build rechazado, se mantiene la versión anterior):**")
        block += [f"  - {i}" for i in issues]
    block.append("")

    existing = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else "# Baskio Dashboard — Changelog\n\n"
    changelog_path.write_text(existing + "\n".join(block) + "\n", encoding="utf-8")


def load_prev_dataset(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
