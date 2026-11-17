"""
TAURIVON Math Engine
Універсальний калькулятор: мішані числа, дроби, десяткові числа,
відсотки та степені.

Запуск:
    python taurivon_math_engine.py

Потрібен Python 3.9+; додаткові бібліотеки не потрібні.
"""

import ast
import re
import tkinter as tk
from tkinter import ttk, messagebox
from fractions import Fraction


APP_NAME = "TAURIVON Math Engine"


def prepare_expression(expression: str) -> str:
    """Перетворює математичний запис на безпечний вираз для обчислення."""
    expr = expression.strip()
    if not expr:
        raise ValueError("Введи математичний вираз.")

    # Зручні математичні символи.
    expr = expr.replace("×", "*").replace("·", "*").replace("÷", "/")
    expr = expr.replace("−", "-").replace("^", "**")

    # Мішане число: 2 1/3 -> (2 + 1/3).
    expr = re.sub(
        r"(?<![\w.])(\d+)\s+(\d+)\s*/\s*(\d+)(?![\w.])",
        r"(\1+\2/\3)",
        expr,
    )

    # Відсоток: 25% -> (25/100).
    # Підтримує числа та прості вирази в дужках: (3+2)%.
    expr = re.sub(
        r"(\d+(?:\.\d+)?|\([^()]*\))\s*%",
        r"(\1/100)",
        expr,
    )

    # Дозволяємо запис 2(3+4) як 2*(3+4), а також 2π тут не підтримується.
    expr = re.sub(r"(\d|\))\s*(\()", r"\1*\2", expr)
    return expr


def evaluate_node(node):
    """Обчислює лише дозволені AST-вузли, не використовуючи eval()."""
    if isinstance(node, ast.Expression):
        return evaluate_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise ValueError("Логічні значення не підтримуються.")
        if isinstance(node.value, int):
            return Fraction(node.value)
        if isinstance(node.value, float):
            return Fraction(str(node.value))
        raise ValueError("Дозволені лише числа.")

    if isinstance(node, ast.UnaryOp):
        value = evaluate_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
        raise ValueError("Непідтримуваний знак.")

    if isinstance(node, ast.BinOp):
        left = evaluate_node(node.left)
        right = evaluate_node(node.right)

        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("На нуль ділити не можна.")
            return left / right
        if isinstance(node.op, ast.Pow):
            if right.denominator != 1:
                raise ValueError("Поки що степінь має бути цілим числом.")
            power = right.numerator
            if abs(power) > 1000:
                raise ValueError("Степінь завеликий (максимум 1000).")
            if left == 0 and power < 0:
                raise ZeroDivisionError("Нуль не можна підносити до від’ємного степеня.")
            return left ** power

    raise ValueError("У виразі є непідтримувана операція.")


def calculate(expression: str) -> Fraction:
    prepared = prepare_expression(expression)
    try:
        tree = ast.parse(prepared, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Перевір правильність запису виразу.") from exc
    result = evaluate_node(tree)
    if abs(result.numerator) > 10**100 or result.denominator > 10**100:
        raise ValueError("Результат надто великий.")
    return result


def format_result(value: Fraction) -> str:
    """Показує точний дріб і десяткове наближення."""
    if value.denominator == 1:
        return str(value.numerator)

    exact = f"{value.numerator}/{value.denominator}"
    decimal = f"{float(value):.12f}".rstrip("0").rstrip(".")
    if len(decimal) > 30:
        decimal = decimal[:30]
    return f"{exact}   ≈   {decimal}"


class TaurivonCalculator:
    BG = "#0b1020"
    PANEL = "#141d33"
    PANEL_2 = "#1b2945"
    TEXT = "#edf3ff"
    MUTED = "#9aabc8"
    ACCENT = "#55d6be"
    ACCENT_DARK = "#163f43"

    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("760x650")
        self.root.minsize(620, 560)
        self.root.configure(bg=self.BG)

        self.expression = tk.StringVar()
        self.result_text = tk.StringVar(value="Тут з’явиться результат")
        self.history_items = []

        self.build_ui()
        self.root.bind("<Return>", lambda _event: self.on_calculate())
        self.root.bind("<Escape>", lambda _event: self.clear())

    def build_ui(self):
        outer = tk.Frame(self.root, bg=self.BG, padx=26, pady=22)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=self.BG)
        header.pack(fill="x", pady=(0, 18))

        tk.Label(
            header, text="TAURIVON", bg=self.BG, fg=self.ACCENT,
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w")
        tk.Label(
            header, text="Math Engine", bg=self.BG, fg=self.TEXT,
            font=("Segoe UI", 27, "bold")
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Універсальний калькулятор дробів, відсотків і степенів",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 10)
        ).pack(anchor="w", pady=(3, 0))

        panel = tk.Frame(outer, bg=self.PANEL, padx=18, pady=18)
        panel.pack(fill="x")

        tk.Label(
            panel, text="МАТЕМАТИЧНИЙ ВИРАЗ", bg=self.PANEL,
            fg=self.MUTED, font=("Segoe UI", 9, "bold")
        ).pack(anchor="w")

        entry = tk.Entry(
            panel, textvariable=self.expression, bg=self.PANEL_2,
            fg=self.TEXT, insertbackground=self.TEXT, relief="flat",
            font=("Consolas", 20), bd=0
        )
        entry.pack(fill="x", ipady=13, pady=(8, 12))
        entry.focus_set()

        buttons = tk.Frame(panel, bg=self.PANEL)
        buttons.pack(fill="x")

        self.make_button(buttons, "Обчислити", self.on_calculate, primary=True).pack(
            side="left", padx=(0, 8)
        )
        self.make_button(buttons, "Очистити", self.clear).pack(side="left")

        result_panel = tk.Frame(outer, bg=self.PANEL, padx=18, pady=16)
        result_panel.pack(fill="x", pady=14)

        tk.Label(
            result_panel, text="РЕЗУЛЬТАТ", bg=self.PANEL,
            fg=self.MUTED, font=("Segoe UI", 9, "bold")
        ).pack(anchor="w")
        tk.Label(
            result_panel, textvariable=self.result_text, bg=self.PANEL,
            fg=self.ACCENT, font=("Segoe UI", 17, "bold"),
            wraplength=650, justify="left"
        ).pack(anchor="w", pady=(9, 0))

        lower = tk.Frame(outer, bg=self.BG)
        lower.pack(fill="both", expand=True)

        help_panel = tk.Frame(lower, bg=self.PANEL, padx=16, pady=14)
        help_panel.pack(side="left", fill="both", expand=True, padx=(0, 7))
        history_panel = tk.Frame(lower, bg=self.PANEL, padx=16, pady=14)
        history_panel.pack(side="left", fill="both", expand=True, padx=(7, 0))

        tk.Label(
            help_panel, text="ПРИКЛАДИ", bg=self.PANEL,
            fg=self.TEXT, font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 8))

        examples = [
            ("Мішане число", "2 1/3 + 1/2"),
            ("Десяткові дроби", "0.75 * 1/2"),
            ("Відсотки", "200 * 15%"),
            ("Степені", "(3/4)^2 + 2^3"),
            ("Усе разом", "2 1/3 + 0.75 * 1/2"),
        ]
        for label, sample in examples:
            row = tk.Frame(help_panel, bg=self.PANEL)
            row.pack(fill="x", pady=3)
            tk.Label(
                row, text=label, bg=self.PANEL, fg=self.MUTED,
                font=("Segoe UI", 9), anchor="w"
            ).pack(anchor="w")
            sample_button = tk.Button(
                row, text=sample, command=lambda s=sample: self.set_example(s),
                bg=self.PANEL_2, fg=self.TEXT, activebackground=self.ACCENT_DARK,
                activeforeground=self.TEXT, relief="flat", bd=0,
                font=("Consolas", 10), anchor="w", padx=8, pady=5, cursor="hand2"
            )
            sample_button.pack(fill="x")

        tk.Label(
            history_panel, text="ІСТОРІЯ", bg=self.PANEL,
            fg=self.TEXT, font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 8))

        self.history = tk.Listbox(
            history_panel, bg=self.PANEL_2, fg=self.TEXT,
            selectbackground=self.ACCENT_DARK, relief="flat",
            font=("Consolas", 9), height=11, activestyle="none"
        )
        self.history.pack(fill="both", expand=True)

        footer = tk.Label(
            outer,
            text="Підтримка: +  −  ×  ÷  ^  дроби  мішані числа  відсотки",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)
        )
        footer.pack(anchor="w", pady=(13, 0))

    def make_button(self, parent, label, command, primary=False):
        bg = self.ACCENT if primary else self.PANEL_2
        fg = self.BG if primary else self.TEXT
        return tk.Button(
            parent, text=label, command=command, bg=bg, fg=fg,
            activebackground=self.ACCENT_DARK, activeforeground=self.TEXT,
            relief="flat", bd=0, padx=18, pady=9,
            font=("Segoe UI", 10, "bold"), cursor="hand2"
        )

    def set_example(self, sample):
        self.expression.set(sample)
        self.on_calculate()

    def on_calculate(self):
        raw = self.expression.get()
        try:
            result = calculate(raw)
            formatted = format_result(result)
            self.result_text.set(formatted)
            self.history_items.insert(0, f"{raw} = {formatted}")
            self.history_items = self.history_items[:30]
            self.history.delete(0, tk.END)
            for item in self.history_items:
                self.history.insert(tk.END, item)
        except Exception as exc:
            messagebox.showerror("TAURIVON Math Engine", str(exc))

    def clear(self):
        self.expression.set("")
        self.result_text.set("Тут з’явиться результат")


def main():
    root = tk.Tk()
    TaurivonCalculator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
