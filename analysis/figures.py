# %% [markdown]
# # Figures and policy table
#
# Reads `results/read_rates.csv` (written by `read_rates.py`) and produces:
# - `results/policies.csv`: correct / wrong / rejected per decision policy
# - `results/figures/*-{light,dark}.svg`: static charts sized for fugu.cafe
#   (860px), one per site theme: latte and espresso backgrounds

# %%
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT / "src"))

from checkdigit_vision.domain.checksums import is_valid_ean13, is_valid_iban  # noqa: E402
from checkdigit_vision.domain.degrade import LEVELS  # noqa: E402

RES = ROOT / "results"
FIG = RES / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# blog tokens per theme (css/style.css light-dark() pairs); line colors keep
# their hue and are darkened on latte to stay >= 3:1 against the surface
THEMES = {
    "light": {"surface": "#f6eee2", "ink": "#2a1e16", "muted": "#6e5a4b", "grid": "#d5c4ae",
              "blue": "#2a6cc8", "orange": "#b84a1c", "aqua": "#0f7a55"},
    "dark": {"surface": "#17110d", "ink": "#eadccb", "muted": "#9c8a7a", "grid": "#3a2d23",
             "blue": "#3987e5", "orange": "#d95926", "aqua": "#199e70"},
}

UNITS = {
    "blur": "gaussian sigma (px)", "rotation": "degrees", "perspective": "corner jitter (%)",
    "noise": "noise sd (gray levels)", "jpeg": "JPEG quality", "downscale": "resize factor",
    "occlusion": "barcode covered (%)",
}
PERCENT_AXES = {"perspective", "occlusion"}


def tick_labels(kind, levels):
    if kind in PERCENT_AXES:
        return [f"{v * 100:g}" for v in levels]
    return [f"{v:g}" for v in levels]


VALID = {"ean": is_valid_ean13, "iban": is_valid_iban}

# codes must stay strings: pandas would parse "0123..." as an int and drop the zero
_text_cols = [f"{p}_{f}_read" for p in ("sym", "raw", "pre") for f in ("ean", "iban")] + ["ean", "iban"]
df = pd.read_csv(RES / "read_rates.csv", dtype={c: str for c in _text_cols},
                 keep_default_na=False, na_values=[""])


# %% [markdown]
# ## Decision policies
#
# Same reads, four ways of deciding. Each adds one source of evidence:
# symbol only, + OCR on the preprocessed image, + OCR on the raw image,
# + checksum repair (only when it leaves a single candidate).

# %%
def policy_outcome(row, field, use_pre, use_raw, use_repair):
    truth = row[field]
    valid = VALID[field]
    sym = row[f"sym_{field}_read"]
    if isinstance(sym, str) and valid(sym):
        return "correct" if sym == truth else "wrong"
    names = [n for n, on in (("pre", use_pre), ("raw", use_raw)) if on]
    for n in names:
        read = row[f"{n}_{field}_read"]
        if isinstance(read, str) and row[f"{n}_{field}_status"] == "valid":
            return "correct" if read == truth else "wrong"
    if use_repair:
        for n in names:
            if row[f"{n}_{field}_n"] == 1:
                return "correct" if row[f"{n}_{field}_hit"] else "wrong"
    return "rejected"


POLICIES = {
    "symbol only": (False, False, False),
    "+ OCR (preprocessed)": (True, False, False),
    "+ OCR (raw)": (True, True, False),
    "+ checksum repair": (True, True, True),
}

rows = []
for field in ("ean", "iban"):
    for name, flags in POLICIES.items():
        out = df.apply(lambda r: policy_outcome(r, field, *flags), axis=1)
        counts = out.value_counts()
        rows.append({"field": field, "policy": name, "images": len(out),
                     **{k: int(counts.get(k, 0)) for k in ("correct", "wrong", "rejected")}})
policies = pd.DataFrame(rows)
policies.to_csv(RES / "policies.csv", index=False)

# sanity: the last policy is exactly what the pipeline decided
for field in ("ean", "iban"):
    last = policies[(policies.field == field) & (policies.policy == "+ checksum repair")].iloc[0]
    pipe = df[f"final_{field}_outcome"].value_counts()
    assert all(last[k] == pipe.get(k, 0) for k in ("correct", "wrong", "rejected")), field

print(policies.to_string(index=False))


# %% [markdown]
# ## Read rates per degradation

# %%
def style(ax, t):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(t["grid"])
    ax.tick_params(colors=t["muted"], labelsize=8)
    ax.grid(axis="y", color=t["grid"], linewidth=0.8)
    ax.set_ylim(-0.03, 1.05)
    ax.set_yticks([0, 0.5, 1])
    ax.set_yticklabels(["0%", "50%", "100%"])


def rate_by_level(field, col_fn):
    g = df.groupby(["kind", "level"])
    return g.apply(col_fn, include_groups=False).rename("rate").reset_index()


def ocr_any_ok(g, field):
    return (g[f"raw_{field}_ok"] | g[f"pre_{field}_ok"]).mean()


def small_multiples(field, title, path, t):
    # pipeline first, as a wide band: where it coincides with a thin line
    # (symbol at 100% under rotation, for example) both stay visible
    series = [
        ("pipeline correct", t["aqua"], None, 7, lambda g: (g[f"final_{field}_outcome"] == "correct").mean()),
        ("symbol decoded", t["blue"], "o", 2, lambda g: g[f"sym_{field}_ok"].mean()),
        ("OCR exact (raw or pre)", t["orange"], "s", 2, lambda g: ocr_any_ok(g, field)),
    ]
    data = {name: rate_by_level(field, fn) for name, _, _, _, fn in series}

    fig, axes = plt.subplots(2, 4, figsize=(8.6, 4.6), facecolor=t["surface"])
    for ax, kind in zip(axes.flat, LEVELS):
        style(ax, t)
        levels = LEVELS[kind]
        xs = range(len(levels))
        for name, color, marker, width, _ in series:
            d = data[name][data[name].kind == kind].set_index("level").reindex(levels)
            ax.plot(xs, d.rate, color=color, linewidth=width, marker=marker, markersize=5,
                    markeredgecolor=t["surface"], markeredgewidth=1.2, label=name,
                    alpha=0.55 if marker is None else 1.0, solid_capstyle="round")
        ax.set_xticks(list(xs))
        ax.set_xticklabels(tick_labels(kind, levels))
        ax.set_title(kind, color=t["ink"], fontsize=10, loc="left")
        ax.set_xlabel(UNITS[kind], color=t["muted"], fontsize=7.5)

    legend_ax = axes.flat[-1]
    legend_ax.axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    legend_ax.legend(handles, labels, loc="center", frameon=False, labelcolor=t["ink"], fontsize=9)
    n = int(df.groupby(["kind", "level"]).size().iloc[0])
    fig.suptitle(f"{title}: share of {n} labels per level", color=t["ink"], fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, format="svg", facecolor=t["surface"])
    plt.close(fig)


for theme, t in THEMES.items():
    small_multiples("ean", "EAN-13", FIG / f"ean_read_rates-{theme}.svg", t)
    small_multiples("iban", "IBAN", FIG / f"iban_read_rates-{theme}.svg", t)


# %% [markdown]
# ## Preprocessing is not free: raw vs preprocessed OCR

# %%
def raw_vs_pre(path, t):
    kinds = ["rotation", "blur"]
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 2.9), facecolor=t["surface"])
    for ax, kind in zip(axes, kinds):
        style(ax, t)
        levels = LEVELS[kind]
        xs = range(len(levels))
        sub = df[df.kind == kind].groupby("level")
        for col, name, color, marker in (("raw", "OCR raw", t["blue"], "o"), ("pre", "OCR preprocessed", t["orange"], "s")):
            rate = sub[f"{col}_ean_ok"].mean().reindex(levels)
            ax.plot(xs, rate, color=color, linewidth=2, marker=marker, markersize=5,
                    markeredgecolor=t["surface"], markeredgewidth=1.2, label=name)
        ax.set_xticks(list(xs))
        ax.set_xticklabels(tick_labels(kind, levels))
        ax.set_title(f"EAN-13 OCR, {kind}", color=t["ink"], fontsize=10, loc="left")
        ax.set_xlabel(UNITS[kind], color=t["muted"], fontsize=7.5)
    axes[1].legend(frameon=False, labelcolor=t["ink"], fontsize=9, loc="center left")
    fig.tight_layout()
    fig.savefig(path, format="svg", facecolor=t["surface"])
    plt.close(fig)


for theme, t in THEMES.items():
    raw_vs_pre(FIG / f"ocr_raw_vs_pre-{theme}.svg", t)
print("figures:", sorted(p.name for p in FIG.iterdir()))
