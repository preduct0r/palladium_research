
import os
from pathlib import Path
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment

# --- 1. Шаблон и папка с данными ------------------------------------------------
TEMPLATE_PATH   = Path("Анализ статей (ИИ).xlsx")   # ваш файл-шаблон
OUTPUT_PATH     = Path("Анализ статей (ИИ)_filled.xlsx")
DATA_ROOT       = Path("data")                     # корень со статьями
ANSWERS_DIRNAME = "answers"                        # подпапка с txt

# --- 2. Сопоставление имён файлов → заголовки столбцов ---------------------------
map_names = {
    "comments": "Комментарии",
    "decision": "Принятие решения",
    "commercial_potential": "Коммерческий потенциал внедрения Pd",
    "competitive_advantages": "Конкурентные преимущества Pd",
    "date": "Дата публикации",
    "development_complexity": "Сложность разработки",
    "development_duration": "Длительность разработки",
    "doi": "Ссылка [DOI]",
    "idea": "Идея",
    "implementation_complexity": "Сложность внедрения",
    "journal": "Журнал",
    "market_commercial_potential": "Уровень рыночного потенциала (коммерция)",
    "market_prospects": "Перспективность рынка (разработка)",
    "potential_consumption": "Потенциальное потребление Pd, кг ",
    "palladium_novelty": "Новизна применения Pd",
    "technical_feasibility": "Научно-техническая реализуемость внедрения Pd",
    "technology_development_level": "Уровень развития технологии под которую делается продукт",
    "technology_readiness_level": "Уровень готовности технологии с Pd",
    "technology": "Промышленная технология",
    "type": "Тип проекта",
    "tematic": "Направление (тематика)",
}

# --- 3. Открываем (или создаём) книгу и лист ------------------------------------
if TEMPLATE_PATH.exists():
    wb = load_workbook(TEMPLATE_PATH)
    ws = wb.active
else:                                           # на случай, если шаблона нет
    wb = Workbook()
    ws = wb.active

# --- 4. Записываем строку заголовков (если ещё пусто) ----------------------------
if ws.max_row == 1 and ws.max_column == 1 and ws["A1"].value is None:
    for col, header in enumerate(map_names.values(), start=1):
        ws.cell(row=1, column=col, value=header)

# --- 5. Настраиваем фиксированные размеры ---------------------------------------
COL_WIDTH   = 55     # «символьных» единиц Excel
ROW_HEIGHT  = 115    # пунктов (≈ пиксели / 0.75)

for col_idx in range(1, len(map_names) + 1):
    col_letter = get_column_letter(col_idx)
    ws.column_dimensions[col_letter].width = COL_WIDTH

# --- 6. Наполняем таблицу строками по статьям -----------------------------------
row_idx = ws.max_row + 1   # добавляем после последней непустой строки

for article_dir in sorted(DATA_ROOT.iterdir()):
    answers_folder = article_dir / ANSWERS_DIRNAME
    if not answers_folder.is_dir():
        continue  # пропускаем, если подпапки 'answers' нет

    for col_idx, (fname, _) in enumerate(map_names.items(), start=1):
        txt_path = answers_folder / f"{fname}.txt"
        value = txt_path.read_text(encoding="utf-8").strip() if txt_path.exists() else ""
        cell = ws.cell(row=row_idx, column=col_idx, value=value)
        cell.alignment = Alignment(wrapText=True, vertical="top")

    ws.row_dimensions[row_idx].height = ROW_HEIGHT
    row_idx += 1

# --- 7. Сохраняем результат ------------------------------------------------------
wb.save(OUTPUT_PATH)
print(f"Готово! Файл сохранён как: {OUTPUT_PATH.resolve()}")



