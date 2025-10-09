# PlanBoard
Простое десктоп‑приложение на PyQt5 для планирования задач.

## Возможности
- Добавление, редактирование и удаление задач (CRUD)
- Сортировка по любому столбцу (клик по заголовку)
- Поиск по названию (строка поиска сверху)
- Фильтры:
  - Все
  - Открытые
  - Просроченные
  - На сегодня
  - Выполненные
- Переключение статуса выполнения задачи из контекстного меню
- Настраиваемые столбцы (показ/скрытие, сохранение ширины и порядка)
- Темы: светлая/тёмная (сохранение выбора)
- Сохранение состояния таблицы и окна между запусками

## Горячие клавиши
- F1 — Справка
- F2 — Добавить задачу
- F3 — Редактировать выбранную
- Delete — Удалить выбранную
- F5 — Обновить список
- Двойной клик по строке — редактирование задачи

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
- python -m pip install --upgrade pip
- python -m pip install -r requirements.txt

4) Инициализировать базу (если не создаётся автоматически)
- python -c "from app.db import init_db; init_db(); print('DB OK')"

5) Запустить приложение
- python -m app.main

## Сборка Windows .exe (PyInstaller)
- Убедитесь, что ресурсы добавляются и включена поддержка SVG:
- Пример запуска (Windows, разделитель в --add-data — точка с запятой):
  - .\venv\Scripts\pyinstaller.exe --onefile --windowed ^
    --icon "app\resources\icons\app.ico" ^
    --add-data "app\resources;app\resources" ^
    --hidden-import PyQt5.QtSvg ^
    app\main.py

Совет: поместите команду сборки в build.bat, чтобы не терялись двойные дефисы при копировании.

## Структура проекта
- app/main.py — точка входа приложения
- app/views.py — главное окно, виджеты и титульная панель
- app/db.py — инициализация БД (DDL)
- app/repo.py — доступ к данным (CRUD)
- app/resources — ресурсы (иконки, шрифты и т.п.)
- requirements.txt — зависимости
- .gitignore — исключения для Git

## Частые проблемы и решения
- Qt: “Could not find the Qt platform plugin 'windows'”
  - Запусти в новой сессии PowerShell после активации venv.
  - Очисти переменные окружения QT_PLUGIN_PATH / QT_QPA_PLATFORM_PLUGIN_PATH.
  - Проверь наличие qwindows.dll в venv: PyQt5/Qt/plugins/platforms/qwindows.dll.

- Иконки не отображаются в .exe
  - Добавь поддержку SVG: --hidden-import PyQt5.QtSvg
  - Убедись, что ресурсы включены: --add-data "app\resources;app\resources"
  - В коде используй безопасные пути к ресурсам (sys._MEIPASS для PyInstaller).

- Конструкторы классов
  - Используй __init__ (с двойными подчёркиваниями), а не init.
  - Вызов базового конструктора: super().__init__(parent)

- Обновление зависимостей
  - python -m pip freeze | Out-File -FilePath requirements.txt -Encoding utf8

## Команды разработки
- Обновить зависимости:
  - python -m pip freeze | Out-File -FilePath requirements.txt -Encoding utf8
- Коммиты:
  - git add .
  - git commit -m "Update"
  - git push
