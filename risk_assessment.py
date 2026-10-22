"""Strumento di valutazione del rischio informatico ispirato a ISO 27001.

Legge tre file CSV (asset, rischi, controlli), calcola il livello di ogni
rischio come probabilità x impatto, propone i controlli di ISO/IEC 27001:2022
(Annex A) per i rischi che vanno trattati e produce:
  - un report CSV ordinato dal rischio più alto al più basso;
  - una matrice dei rischi (heatmap) in formato PNG;
  - un riepilogo a terminale.

Uso:
    python risk_assessment.py
    python risk_assessment.py --data data --out output
"""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # nessuna finestra: salva soltanto il file
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# --- Parametri del metodo -------------------------------------------------
# Probabilità e impatto vanno da 1 (molto basso) a 5 (molto alto).
MIN_VALUE, MAX_VALUE = 1, 5

# Soglie sul punteggio (probabilità x impatto, da 1 a 25).
LOW_MAX = 6      # fino a 6   -> Basso
MEDIUM_MAX = 12  # da 7 a 12  -> Medio; oltre 12 -> Alto

LEVEL_COLORS = {"Basso": "#7fc97f", "Medio": "#ffd966", "Alto": "#e06666"}


# --- Calcolo --------------------------------------------------------------
def calculate_score(likelihood: int, impact: int) -> int:
    """Il punteggio di rischio è probabilità per impatto."""
    return likelihood * impact


def risk_level(score: int) -> str:
    """Trasforma il punteggio in un livello: Basso, Medio o Alto."""
    if score <= LOW_MAX:
        return "Basso"
    if score <= MEDIUM_MAX:
        return "Medio"
    return "Alto"


# --- Lettura e controllo dei dati ----------------------------------------
def load_csv(path: Path) -> list[dict]:
    """Legge un CSV e restituisce una lista di dizionari (una riga = un dizionario)."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate(assets: list[dict], risks: list[dict], controls: list[dict]) -> None:
    """Controlla i dati e, se trova errori, li elenca tutti insieme."""
    errors = []
    asset_ids = {a["asset_id"] for a in assets}
    categories = {c["category"] for c in controls}

    for r in risks:
        rid = r["risk_id"]
        if r["asset_id"] not in asset_ids:
            errors.append(f"{rid}: asset '{r['asset_id']}' non presente in assets.csv")
        if r["category"] not in categories:
            errors.append(f"{rid}: categoria '{r['category']}' senza controlli in controls.csv")
        for field in ("likelihood", "impact"):
            try:
                value = int(r[field])
            except ValueError:
                errors.append(f"{rid}: {field} '{r[field]}' non è un numero intero")
                continue
            if not MIN_VALUE <= value <= MAX_VALUE:
                errors.append(f"{rid}: {field} {value} fuori dal range {MIN_VALUE}-{MAX_VALUE}")

    if errors:
        raise ValueError("Dati non validi:\n  - " + "\n  - ".join(errors))


# --- Costruzione del report ----------------------------------------------
def build_report(assets: list[dict], risks: list[dict], controls: list[dict]) -> list[dict]:
    """Unisce i dati, calcola punteggio e livello e sceglie il trattamento."""
    asset_names = {a["asset_id"]: a["name"] for a in assets}

    controls_by_category = defaultdict(list)
    for c in controls:
        controls_by_category[c["category"]].append(c)

    report = []
    for r in risks:
        likelihood, impact = int(r["likelihood"]), int(r["impact"])
        score = calculate_score(likelihood, impact)
        level = risk_level(score)

        if level == "Basso":
            # I rischi bassi si accettano, ma si tengono sotto controllo.
            treatment = "Accettare e monitorare"
            suggested = ""
        else:
            treatment = "Trattare"
            suggested = "; ".join(
                f"{c['control_id']} {c['control_name']}: {c['suggested_action']}"
                for c in controls_by_category[r["category"]]
            )

        report.append(
            {
                "risk_id": r["risk_id"],
                "asset": asset_names[r["asset_id"]],
                "category": r["category"],
                "threat": r["threat"],
                "vulnerability": r["vulnerability"],
                "likelihood": likelihood,
                "impact": impact,
                "score": score,
                "level": level,
                "treatment": treatment,
                "suggested_controls": suggested,
            }
        )

    # Dal rischio più alto al più basso; a parità di punteggio, per identificativo.
    report.sort(key=lambda row: (-row["score"], row["risk_id"]))
    return report


# --- Output ---------------------------------------------------------------
def write_report_csv(report: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(report[0].keys()))
        writer.writeheader()
        writer.writerows(report)


def draw_risk_matrix(report: list[dict], path: Path) -> None:
    """Disegna la matrice 5x5: probabilità in verticale, impatto in orizzontale."""
    cells = defaultdict(list)
    for row in report:
        cells[(row["likelihood"], row["impact"])].append(row["risk_id"])

    fig, ax = plt.subplots(figsize=(8, 7))
    for likelihood in range(MIN_VALUE, MAX_VALUE + 1):
        for impact in range(MIN_VALUE, MAX_VALUE + 1):
            level = risk_level(calculate_score(likelihood, impact))
            ax.add_patch(
                plt.Rectangle(
                    (impact - 0.5, likelihood - 0.5), 1, 1,
                    facecolor=LEVEL_COLORS[level], edgecolor="white", linewidth=2,
                )
            )
            ids = cells.get((likelihood, impact), [])
            if ids:
                ax.text(impact, likelihood, "\n".join(ids), ha="center", va="center",
                        fontsize=9, fontweight="bold")

    ax.set_xlim(MIN_VALUE - 0.5, MAX_VALUE + 0.5)
    ax.set_ylim(MIN_VALUE - 0.5, MAX_VALUE + 0.5)
    ax.set_xticks(range(MIN_VALUE, MAX_VALUE + 1))
    ax.set_yticks(range(MIN_VALUE, MAX_VALUE + 1))
    ax.set_xlabel("Impatto (1 = molto basso, 5 = molto alto)")
    ax.set_ylabel("Probabilità (1 = molto bassa, 5 = molto alta)")
    ax.set_title("Matrice dei rischi")
    ax.set_aspect("equal")
    ax.legend(
        handles=[Patch(facecolor=color, label=level) for level, color in LEVEL_COLORS.items()],
        loc="upper left", bbox_to_anchor=(1.02, 1.0), title="Livello",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def print_summary(report: list[dict]) -> None:
    counts = Counter(row["level"] for row in report)
    print(f"Rischi analizzati: {len(report)}")
    for level in ("Alto", "Medio", "Basso"):
        print(f"  {level}: {counts.get(level, 0)}")
    print("\nI 5 rischi più alti:")
    for row in report[:5]:
        print(f"  {row['risk_id']}  punteggio {row['score']:>2}  {row['level']:<5}  "
              f"{row['asset']}: {row['threat']}")


# --- Programma principale -------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Valutazione del rischio ispirata a ISO 27001")
    parser.add_argument("--data", default="data", help="cartella con i file CSV (default: data)")
    parser.add_argument("--out", default="output", help="cartella di output (default: output)")
    args = parser.parse_args()

    data_dir, out_dir = Path(args.data), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    assets = load_csv(data_dir / "assets.csv")
    risks = load_csv(data_dir / "risks.csv")
    controls = load_csv(data_dir / "controls.csv")

    validate(assets, risks, controls)
    report = build_report(assets, risks, controls)

    write_report_csv(report, out_dir / "risk_report.csv")
    draw_risk_matrix(report, out_dir / "risk_matrix.png")
    print_summary(report)
    print(f"\nFile creati in '{out_dir}': risk_report.csv, risk_matrix.png")


if __name__ == "__main__":
    main()
