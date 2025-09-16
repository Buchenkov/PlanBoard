# PlanBoard
Простое десктоп‑приложение на PyQt5 для планирования задач.

## Требования
- Windows 10/11
- Python 3.8+ (желательно 64‑bit)
- Git (для клонирования)
- Рекомендуется виртуальное окружение venv

## Установка и запуск (PowerShell)
1) Клонировать репозиторий
- git clone https://github.com/Buchenkov/PlanBoard.git
- cd PlanBoard

2) Создать и активировать виртуальное окружение
- python -m venv venv
- .\venv\Scripts\Activate.ps1

3) Установить зависимости
- python -m pip install upgrade pip
- python -m pip install -r requirements.txt

4) Инициализировать базу (если не создаётся автоматически)
- python -c "from app.db import init_db; init_db(); print('DB OK')"

5) Запустить приложение
- python -m app.main

## Структура проекта
- app/main.py — точка входа приложения
- app/views.py — главное окно и виджеты
- app/db.py — инициализация БД (DDL)
- app/repo.py — доступ к данным (CRUD)
- requirements.txt — зависимости
- .gitignore — исключения для Git

## Частые проблемы и решения
- Qt: “Could not find the Qt platform plugin 'windows'”
  - Запусти в новой сессии PowerShell после активации venv.
  - Очисти переменные окружения QT_PLUGIN_PATH / QT_QPA_PLATFORM_PLUGIN_PATH.
  - Проверь, что в venv есть PyQt5/Qt5/plugins/platforms/qwindows.dll.
- Конструкторы классов
  - Используй init (с двойными подчёркиваниями), а не init.
- Обновление зависимостей
  - python -m pip freeze | Out-File -FilePath requirements.txt -Encoding utf8

## Команды разработки
- Обновить зависимости:
  - python -m pip freeze | Out-File -FilePath requirements.txt -Encoding utf8
- Коммиты:
  - git add .
  - git commit -m "Update"
  - git push


