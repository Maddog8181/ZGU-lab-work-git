"""StudyFlow: небольшой список учебных заданий с проверкой сроков."""

import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / "localdata" / "tasks.json"
EXAMPLE_FILE = ROOT / "data" / "example_tasks.json"
DEMO_DATE = date(2026, 11, 23)


def parse_date(value):
    """Проверяет дату и возвращает её в удобном для сравнения виде."""
    try:
        result = date.fromisoformat(value)
        if result.isoformat() == value:
            return result
    except (ValueError, TypeError):
        pass
    raise ValueError("Дата должна существовать и иметь вид ГГГГ-ММ-ДД.")


def load_tasks(path):
    """Читает задачи; повреждённые данные нельзя молча заменить пустым списком."""
    if not path.exists():
        return []
    try:
        tasks = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("Файл заданий повреждён. Исправь его или выбери другой --file.") from None
    if not isinstance(tasks, list):
        raise ValueError("Файл заданий должен содержать список.")
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not {"id", "title", "subject", "due", "done"} <= task.keys():
            raise ValueError("В файле есть запись без обязательных полей задания.")
        if type(task["id"]) is not int or task["id"] < 1 or task["id"] in ids:
            raise ValueError("Номера заданий должны быть положительными и уникальными.")
        if any(not isinstance(task[k], str) or not task[k].strip() for k in ("title", "subject")):
            raise ValueError("Название задания и предмет не могут быть пустыми.")
        if type(task["done"]) is not bool:
            raise ValueError("Отметка выполнения должна быть true или false.")
        parse_date(task["due"])
        ids.add(task["id"])
    return tasks


def save_tasks(path, tasks):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_task(tasks, title, subject, due):
    title, subject = title.strip(), subject.strip()
    if not title or not subject:
        raise ValueError("Укажи непустые название задания и предмет.")
    parse_date(due)
    task = {"id": max((t["id"] for t in tasks), default=0) + 1,
            "title": title, "subject": subject, "due": due, "done": False}
    tasks.append(task)
    return task


def complete_task(tasks, task_id):
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            return task
    raise ValueError(f"Задание с номером {task_id} не найдено.")


def task_status(task, today):
    if task["done"]:
        return "готово"
    deadline = parse_date(task["due"])
    if deadline < today:
        return "просрочено"
    return "сегодня" if deadline == today else "ожидает"


def summarize(tasks, today):
    completed = sum(task["done"] for task in tasks)
    return {"total": len(tasks), "completed": completed,
            "pending": len(tasks) - completed,
            "overdue": sum(task_status(task, today) == "просрочено" for task in tasks)}


def show_tasks(tasks, today):
    if not tasks:
        print("Заданий пока нет. Добавь первое командой add.")
    for task in sorted(tasks, key=lambda item: (item["due"], item["id"])):
        print(f'[{task["id"]}] {task["title"]} | {task["subject"]} | '
              f'срок: {task["due"]} | {task_status(task, today)}')


def show_summary(tasks, today):
    result = summarize(tasks, today)
    print(f'Всего: {result["total"]} | Готово: {result["completed"]} | '
          f'Осталось: {result["pending"]} | Просрочено: {result["overdue"]}')


def build_parser():
    parser = argparse.ArgumentParser(description="StudyFlow — учёт учебных заданий и сроков")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help="файл личных заданий")
    commands = parser.add_subparsers(dest="command", title="команды")
    commands.add_parser("demo", help="пример без изменения личных данных (по умолчанию)")
    commands.add_parser("list", help="список личных заданий по срокам")
    commands.add_parser("summary", help="количество готовых и просроченных заданий")
    adding = commands.add_parser("add", help="добавить задание")
    adding.add_argument("title", help="название задания в кавычках")
    adding.add_argument("--subject", required=True, help="учебный предмет")
    adding.add_argument("--due", required=True, help="срок в формате ГГГГ-ММ-ДД")
    done = commands.add_parser("done", help="отметить задание выполненным")
    done.add_argument("id", type=int, help="номер задания")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command in (None, "demo"):
            tasks = load_tasks(EXAMPLE_FILE)
            print(f"StudyFlow — демонстрация на дату {DEMO_DATE}; личные данные не изменяются.")
            show_tasks(tasks, DEMO_DATE)
            show_summary(tasks, DEMO_DATE)
            return 0
        tasks = load_tasks(args.file)
        today = date.today()
        if args.command == "add":
            task = add_task(tasks, args.title, args.subject, args.due)
            save_tasks(args.file, tasks)
            print(f'Добавлено задание №{task["id"]}: {task["title"]}')
        elif args.command == "done":
            task = complete_task(tasks, args.id)
            save_tasks(args.file, tasks)
            print(f'Выполнено задание №{task["id"]}: {task["title"]}')
        elif args.command == "list":
            print(f"StudyFlow — задания на {today}")
            show_tasks(tasks, today)
        elif args.command == "summary":
            print(f"StudyFlow — сводка на {today}")
            show_summary(tasks, today)
        return 0
    except (ValueError, OSError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
