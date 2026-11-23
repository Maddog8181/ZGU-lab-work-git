"""Проверки сроков, сохранения и обработки ошибок StudyFlow."""

from contextlib import redirect_stdout, redirect_stderr
from datetime import date
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.main import add_task, complete_task, load_tasks, main, show_tasks, summarize, task_status


class StudyFlowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "tasks.json"
        self.today = date(2026, 11, 23)

    def run_cli(self, *arguments):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = main(["--file", str(self.path), *arguments])
        return result, out.getvalue(), err.getvalue()

    def test_deadline_boundaries_and_completed_tasks(self):
        tasks = []
        for due in ("2026-11-22", "2026-11-23", "2026-11-24", "2026-11-20"):
            add_task(tasks, "Учебное задание", "ИТ", due)
        complete_task(tasks, 4)
        self.assertEqual([task_status(task, self.today) for task in tasks],
                         ["просрочено", "сегодня", "ожидает", "готово"])
        self.assertEqual(summarize(tasks, self.today),
                         {"total": 4, "completed": 1, "pending": 3, "overdue": 1})

    def test_empty_summary(self):
        self.assertEqual(summarize([], self.today),
                         {"total": 0, "completed": 0, "pending": 0, "overdue": 0})

    def test_add_trims_fields_and_assigns_distinct_ids(self):
        tasks = []
        first = add_task(tasks, "  Отчёт  ", " ИТ ", "2026-11-24")
        second = add_task(tasks, "Практика", "ИТ", "2026-11-25")
        self.assertEqual((first["title"], first["subject"]), ("Отчёт", "ИТ"))
        self.assertEqual((first["id"], second["id"]), (1, 2))
        self.assertFalse(first["done"])

    def test_invalid_add_does_not_modify_list(self):
        for title, subject, due in ((" ", "ИТ", "2026-11-24"),
                                    ("Отчёт", " ", "2026-11-24"),
                                    ("Отчёт", "ИТ", "2026-02-30"),
                                    ("Отчёт", "ИТ", "20261124")):
            with self.subTest(title=title, subject=subject, due=due):
                tasks = []
                with self.assertRaises(ValueError):
                    add_task(tasks, title, subject, due)
                self.assertEqual(tasks, [])

    def test_add_and_done_persist_between_invocations(self):
        self.assertEqual(self.run_cli("add", "Отчёт", "--subject", "ИТ",
                                      "--due", "2026-11-24")[0], 0)
        self.assertFalse(load_tasks(self.path)[0]["done"])
        self.assertEqual(self.run_cli("done", "1")[0], 0)
        self.assertTrue(load_tasks(self.path)[0]["done"])
        self.assertEqual(self.run_cli("done", "1")[0], 0)
        self.assertEqual(len(load_tasks(self.path)), 1)

    def test_unknown_id_preserves_saved_file(self):
        self.run_cli("add", "Отчёт", "--subject", "ИТ", "--due", "2026-11-24")
        before = self.path.read_bytes()
        code, _, error = self.run_cli("done", "99")
        self.assertEqual(code, 1)
        self.assertIn("не найдено", error)
        self.assertEqual(self.path.read_bytes(), before)

    def test_broken_json_is_not_overwritten(self):
        self.path.write_text('{"unfinished":', encoding="utf-8")
        before = self.path.read_bytes()
        code, _, error = self.run_cli("add", "Отчёт", "--subject", "ИТ", "--due", "2026-11-24")
        self.assertEqual(code, 1)
        self.assertIn("повреждён", error)
        self.assertEqual(self.path.read_bytes(), before)

    def test_incorrect_record_is_not_overwritten(self):
        self.path.write_text('[{"id": 1}]', encoding="utf-8")
        before = self.path.read_bytes()
        code, _, error = self.run_cli("done", "1")
        self.assertEqual(code, 1)
        self.assertIn("обязательных полей", error)
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_date_does_not_create_file(self):
        code, _, error = self.run_cli("add", "Отчёт", "--subject", "ИТ", "--due", "31.12.2026")
        self.assertEqual(code, 1)
        self.assertIn("ГГГГ-ММ-ДД", error)
        self.assertFalse(self.path.exists())

    def test_demo_without_arguments_does_not_create_personal_file(self):
        with patch("src.main.DEFAULT_FILE", self.path):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main([]), 0)
        self.assertIn("демонстрация на дату 2026-11-23", out.getvalue())
        self.assertIn("Всего: 4 | Готово: 1 | Осталось: 3 | Просрочено: 1", out.getvalue())
        self.assertFalse(self.path.exists())

    def test_list_is_sorted_by_deadline(self):
        tasks = []
        add_task(tasks, "Позднее", "ИТ", "2026-12-01")
        add_task(tasks, "Раньше", "ИТ", "2026-11-24")
        out = io.StringIO()
        with redirect_stdout(out):
            show_tasks(tasks, self.today)
        self.assertLess(out.getvalue().index("Раньше"), out.getvalue().index("Позднее"))


if __name__ == "__main__":
    unittest.main()
