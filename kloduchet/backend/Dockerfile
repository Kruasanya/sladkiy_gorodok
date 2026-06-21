FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Структура внутри контейнера повторяет структуру репозитория
# (.../sladkiy_gorodok/kloduchet/backend), потому что адаптеры пайплайнов
# (pipelines/*.py) находят `Данные/Пайплайны обработки данных` по относительному
# пути от своего файла — см. tech_spec.md, раздел 6.3.
WORKDIR /workspace/kloduchet/backend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
