"""Build all tables and figures in outputs/."""
from pathlib import Path
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import esg  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT, FIG = ROOT / "outputs", ROOT / "outputs" / "figures"
C = ["#1D4E89", "#00A6A6", "#F6AE2D", "#E4572E", "#6A4C93"]
CREDIT = "Mohammad Rabbani | github.com/Rabbani-bot"


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    (ROOT / "data").mkdir(exist_ok=True)
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                         "grid.color": "#E6E8EC", "savefig.dpi": 150, "savefig.bbox": "tight"})
    raw = esg.generate()
    raw.round(3).to_csv(ROOT / "data" / "activity_quarterly.csv", index=False)
    clean, dq = esg.validate(raw)
    m = esg.metrics(clean)
    m.round(2).to_csv(OUT / "tcfd_metrics_by_year.csv")
    latest = m.index.max()
    exp = esg.carbon_exposure(m.loc[latest, "s12_market_t"], ebitda_musd=0.15 * m.loc[latest, "revenue_musd"])
    exp.round(2).to_csv(OUT / "carbon_price_exposure.csv", index=False)
    summary = {"latest_year": int(latest), "s12_market_t": round(float(m.loc[latest, "s12_market_t"]), 1),
               "change_vs_base_pct": round(float(100 * (m.loc[latest, "s12_market_t"] / m.loc[esg.BASE_YEAR, "s12_market_t"] - 1)), 1),
               "vs_target_path_pct": round(float(m.loc[latest, "vs_target_pct"]), 1),
               "intensity_t_per_musd": round(float(m.loc[latest, "intensity_t_per_musd"]), 2),
               "re_share_pct": round(float(m.loc[latest, "re_share_pct"]), 1),
               "data_quality": {k: dq[k] for k in ["records", "gaps", "completeness_pct"]}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    ax[0].bar(m.index, m.scope1_t / 1e3, color=C[0], label="Scope 1")
    ax[0].bar(m.index, m.scope2_market_t / 1e3, bottom=m.scope1_t / 1e3, color=C[1], label="Scope 2 (market)")
    ax[0].plot(m.index, (m.scope1_t + m.scope2_location_t) / 1e3, "k_", ms=28, mew=2, label="S1 + S2 location-based")
    ax[0].plot(m.index, m.target_path_t / 1e3, "--", color=C[3], lw=2, label="42% by 2030 path")
    ax[0].set_title("Scope 1 + 2 emissions vs target path", loc="left", fontweight="bold"); ax[0].set_ylabel("kt CO2e"); ax[0].legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    ax[1].plot(m.index, m.intensity_t_per_musd, marker="o", color=C[4], lw=2.4)
    ax2 = ax[1].twinx(); ax2.bar(m.index, m.re_share_pct, alpha=0.25, color=C[2]); ax2.set_ylabel("Renewable electricity (%)"); ax2.grid(False)
    ax[1].set_ylabel("t CO2e per USD m revenue"); ax[1].set_title("Intensity and renewable share", loc="left", fontweight="bold")
    fig.text(0.995, 0.005, CREDIT, ha="right", fontsize=8, color="#777")
    fig.savefig(FIG / "01_metrics_targets.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.barh(exp.scenario, exp.pct_of_ebitda, color=[C[1], C[2], C[3]])
    for i, r in exp.iterrows():
        ax.text(r.pct_of_ebitda + 0.1, i, f"USD {r.cost_musd:.1f}m ({r.pct_of_ebitda:.1f}% of EBITDA) at USD {r.price_usd_t}/t", va="center", fontsize=9)
    ax.set_xlabel("Carbon cost as % of EBITDA"); ax.set_xlim(0, exp.pct_of_ebitda.max() * 1.9)
    ax.set_title(f"Transition-risk exposure, {latest} Scope 1+2 (scenario price assumptions)", loc="left", fontweight="bold")
    fig.text(0.995, 0.005, CREDIT, ha="right", fontsize=8, color="#777")
    fig.savefig(FIG / "02_carbon_price_exposure.png"); plt.close(fig)
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
