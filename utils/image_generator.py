from PIL import Image, ImageDraw, ImageFont
import random
import matplotlib.pyplot as plt
import io
import numpy as np


def generate_schulte_grid_bytes() -> bytes:
    numbers = list(range(1, 26))
    random.shuffle(numbers)

    cell_size = 100
    img_size = cell_size * 5

    img = Image.new("RGB", (img_size, img_size), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except:
        font = ImageFont.load_default()

    for i in range(5):
        for j in range(5):
            x1 = j * cell_size
            y1 = i * cell_size
            x2 = x1 + cell_size
            y2 = y1 + cell_size

            draw.rectangle([x1, y1, x2, y2], outline="black", width=2)

            num = numbers[i * 5 + j]
            text = str(num)

            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            text_x = x1 + (cell_size - text_width) // 2
            text_y = y1 + (cell_size - text_height) // 2

            draw.text((text_x, text_y), text, fill="black", font=font)

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    return img_bytes.getvalue()


def generate_radar_chart_bytes(scores: dict) -> bytes:
    categories = ['Внимание', 'Память', 'Мышление', 'Восприятие', 'Воображение']
    values = [
        scores.get('attention', 0),
        scores.get('memory', 0),
        scores.get('thinking', 0),
        scores.get('perception', 0),
        scores.get('imagination', 0)
    ]

    values += values[:1]

    angles = [n / float(len(categories)) * 2 * np.pi for n in range(len(categories))]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    ax.plot(angles, values, 'o-', linewidth=2, color='#2196F3', markersize=8)
    ax.fill(angles, values, alpha=0.25, color='#2196F3')

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=12)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], size=10)
    ax.set_ylabel('Баллы', size=10)

    ax.grid(True, linestyle='--', alpha=0.7)

    plt.title('Когнитивные способности', size=14, pad=20)

    for i, (angle, value) in enumerate(zip(angles[:-1], values[:-1])):
        ax.text(angle, value + 5, str(int(value)),
                ha='center', va='center', size=10, weight='bold')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    buf.seek(0)

    return buf.getvalue()


def generate_radar_chart_bytes_with_comparison(current_scores: dict, previous_scores: dict = None) -> bytes:
    categories = ['Внимание', 'Память', 'Мышление', 'Восприятие', 'Воображение']
    current_values = [
        current_scores.get('attention', 0),
        current_scores.get('memory', 0),
        current_scores.get('thinking', 0),
        current_scores.get('perception', 0),
        current_scores.get('imagination', 0)
    ]
    current_values += current_values[:1]

    angles = [n / float(len(categories)) * 2 * np.pi for n in range(len(categories))]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    ax.plot(angles, current_values, 'o-', linewidth=2, color='#2196F3', markersize=8, label='Текущий')
    ax.fill(angles, current_values, alpha=0.25, color='#2196F3')

    if previous_scores:
        previous_values = [
            previous_scores.get('attention', 0),
            previous_scores.get('memory', 0),
            previous_scores.get('thinking', 0),
            previous_scores.get('perception', 0),
            previous_scores.get('imagination', 0)
        ]
        previous_values += previous_values[:1]
        ax.plot(angles, previous_values, 'o-', linewidth=2, color='#FF9800', markersize=8, label='Предыдущий',
                alpha=0.7)
        ax.fill(angles, previous_values, alpha=0.15, color='#FF9800')
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=12)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], size=10)
    ax.grid(True, linestyle='--', alpha=0.7)
    plt.title('Динамика когнитивных способностей', size=14, pad=20)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    buf.seek(0)

    return buf.getvalue()