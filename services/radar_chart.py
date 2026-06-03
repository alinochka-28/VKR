import io
import logging
import os
import tempfile
import uuid
from typing import Dict, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)

RADAR_ORDER = ["attention", "perception", "memory", "thinking", "imagination"]
RADAR_LABELS = {
    "attention": "Внимание",
    "perception": "Восприятие",
    "memory": "Память",
    "thinking": "Мышление",
    "imagination": "Воображение",
}


def generate_radar_chart_10(
    scores: Dict[str, float],
    title: str = "Когнитивные способности",
    subtitle: Optional[str] = None,
) -> bytes:

    categories = [RADAR_LABELS[k] for k in RADAR_ORDER]
    values = [float(scores.get(k, 0) or 0) for k in RADAR_ORDER]

    values_closed = values + values[:1]
    angles = [n / float(len(categories)) * 2 * np.pi for n in range(len(categories))]
    angles_closed = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    ax.plot(angles_closed, values_closed, "o-", linewidth=2, color="#2196F3", markersize=8)
    ax.fill(angles_closed, values_closed, alpha=0.25, color="#2196F3")

    ax.set_xticks(angles)
    ax.set_xticklabels(categories, size=12)
    ax.set_ylim(0, 10)
    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_yticklabels(["2", "4", "6", "8", "10"], size=9)
    ax.grid(True, linestyle="--", alpha=0.7)

    for angle, value in zip(angles, values):
        offset = -0.6 if value >= 9.5 else 0.4
        ax.text(
            angle, value + offset, f"{value:.1f}",
            ha="center", va="center", size=10, weight="bold",
        )

    full_title = title if not subtitle else f"{title}\n{subtitle}"
    plt.title(full_title, size=14, pad=20)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_radar_chart_with_emotion(
    scores: Dict[str, float],
    adjusted_scores: Dict[str, float],
    emotion_label: str,
    title: str = "Когнитивные способности с учётом эмоций",
) -> bytes:
    categories = [RADAR_LABELS[k] for k in RADAR_ORDER]
    values_raw = [float(scores.get(k, 0) or 0) for k in RADAR_ORDER]
    values_adj = [float(adjusted_scores.get(k, 0) or 0) for k in RADAR_ORDER]

    angles = [n / float(len(categories)) * 2 * np.pi for n in range(len(categories))]
    raw_closed = values_raw + values_raw[:1]
    adj_closed = values_adj + values_adj[:1]
    angles_closed = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    ax.plot(
        angles_closed, raw_closed,
        "o-", linewidth=2, color="#2196F3", markersize=7,
        label="Результат теста",
    )
    ax.fill(angles_closed, raw_closed, alpha=0.15, color="#2196F3")

    ax.plot(
        angles_closed, adj_closed,
        "s--", linewidth=2, color="#FF6F00", markersize=7,
        label=f"С учётом: «{emotion_label}»",
    )
    ax.fill(angles_closed, adj_closed, alpha=0.15, color="#FF6F00")

    ax.set_xticks(angles)
    ax.set_xticklabels(categories, size=11)
    ax.set_ylim(0, 10)
    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_yticklabels(["2", "4", "6", "8", "10"], size=9)
    ax.grid(True, linestyle="--", alpha=0.7)

    for angle, val_raw, val_adj in zip(angles, values_raw, values_adj):
        offset = -0.6 if val_adj >= 9.5 else 0.5
        color = "#FF6F00" if val_adj != val_raw else "#2196F3"
        ax.text(
            angle, val_adj + offset, f"{val_adj:.1f}",
            ha="center", va="center", size=9, weight="bold", color=color,
        )

    ax.legend(
        loc="upper right",
        bbox_to_anchor=(1.3, 1.1),
        fontsize=9,
        framealpha=0.85,
    )

    plt.title(title, size=13, pad=20)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def save_radar_to_tempfile(
    scores: Dict[str, float],
    title: str = "Когнитивные способности",
    subtitle: Optional[str] = None,
) -> str:
    png = generate_radar_chart_10(scores, title=title, subtitle=subtitle)
    fd, path = tempfile.mkstemp(prefix=f"radar_{uuid.uuid4().hex}_", suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(png)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
    return path


def save_radar_with_emotion_to_tempfile(
    scores: Dict[str, float],
    adjusted_scores: Dict[str, float],
    emotion_label: str,
    title: str = "Когнитивные способности с учётом эмоций",
) -> str:
    png = generate_radar_chart_with_emotion(
        scores, adjusted_scores, emotion_label, title=title
    )
    fd, path = tempfile.mkstemp(
        prefix=f"radar_emotion_{uuid.uuid4().hex}_", suffix=".png"
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(png)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
    return path