
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
