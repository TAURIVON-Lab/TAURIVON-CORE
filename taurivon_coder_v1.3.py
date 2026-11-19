from __future__ import annotations

import codecs
import os
import re
import shutil
import sys
import tempfile
import webbrowser
from pathlib import Path

from PySide6.QtCore import (
    QDir, QModelIndex, QProcess, QProcessEnvironment, QRect, QSize, Qt, QTimer
)
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QIcon, QKeySequence, QPainter, QShortcut,
    QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextFormat
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QStatusBar, QTabWidget, QTextEdit, QTreeView, QVBoxLayout,
    QWidget
)

# У PySide6 (Qt 6) QFileSystemModel знаходиться в QtGui, у старіших збірках — у QtWidgets.
try:
    from PySide6.QtGui import QFileSystemModel
except ImportError:  # pragma: no cover
    from PySide6.QtWidgets import QFileSystemModel

# Необов'язкова залежність: видалення у кошик (pip install send2trash).
try:
    from send2trash import send2trash
except ImportError:  # pragma: no cover
    send2trash = None


APP_NAME = "TAURIVON Coder"
APP_VERSION = "1.3"


def resource_path(relative_path: str) -> str:
    """Повертає коректний шлях до ресурсів як у Python, так і всередині зібраного .exe."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def norm(path: str) -> str:
    """Нормалізований шлях для порівнянь (регістр на Windows, слеші, відносні шляхи)."""
    return os.path.normcase(os.path.abspath(path))


def path_inside(child: str, parent: str) -> bool:
    c, p = norm(child), norm(parent)
    return c == p or c.startswith(p + os.sep)


LANG_PY = "Python (.py)"
LANG_HTML = "HTML (.html)"
LANG_CSS = "CSS (.css)"
LANG_JS = "JavaScript (.js)"
LANG_CPP = "C++ (.cpp)"
LANG_TXT = "Текст (.txt)"

LANG_EXTENSIONS = {
    LANG_PY: ".py",
    LANG_HTML: ".html",
    LANG_CSS: ".css",
    LANG_JS: ".js",
    LANG_CPP: ".cpp",
    LANG_TXT: ".txt",
}


def detect_language(path: str) -> str | None:
    ext = os.path.splitext(path)[1].lower()
    for name, lang_ext in LANG_EXTENSIONS.items():
        if lang_ext == ext:
            return name
    return None


# Типи файлів, які безпечно показувати в редакторі як текстові файли проєкту.
PROJECT_TEXT_EXTENSIONS = {
    ".py", ".pyw", ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".js", ".jsx", ".ts", ".tsx", ".json", ".jsonc", ".txt", ".md",
    ".markdown", ".rst", ".xml", ".svg", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".conf", ".sql", ".c", ".h", ".cc", ".cpp",
    ".cxx", ".hpp", ".java", ".kt", ".go", ".rs", ".php", ".rb",
    ".swift", ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1", ".vue",
    ".svelte", ".csv", ".log", ".properties", ".gradle"
}
PROJECT_TEXT_FILENAMES = {
    "dockerfile", "makefile", "license", "readme", ".gitignore",
    ".gitattributes", ".editorconfig", ".env", ".env.example"
}
PROJECT_IGNORED_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".venv", "venv", "env", "node_modules", "site-packages",
    "dist", "build", "out", "target", "coverage", "vendor", ".next", ".nuxt"
}
MAX_PROJECT_TEXT_FILE_SIZE = 2 * 1024 * 1024  # Файли понад 2 МБ в редактор не завантажуємо.
MAX_AUTO_OPEN_FILES = 30                      # Скільки файлів відкривати автоматично при старті.


# ---------------------------------------------------------------------------
# Шрифти
# ---------------------------------------------------------------------------

_MONO_FAMILY: str | None = None


def mono_font(size: int) -> QFont:
    """Моноширинний шрифт: Consolas, а якщо його немає — найкращий доступний."""
    global _MONO_FAMILY
    if _MONO_FAMILY is None:
        families = set(QFontDatabase.families())
        for name in ("Consolas", "Cascadia Mono", "JetBrains Mono",
                     "DejaVu Sans Mono", "Menlo", "Monaco", "Courier New"):
            if name in families:
                _MONO_FAMILY = name
                break
        else:
            _MONO_FAMILY = QFontDatabase.systemFont(QFontDatabase.FixedFont).family()
    font = QFont(_MONO_FAMILY, size)
    font.setStyleHint(QFont.Monospace)
    return font


# ---------------------------------------------------------------------------
# Читання / запис файлів зі збереженням кодування та переносів рядків
# ---------------------------------------------------------------------------

def read_text_file(path: str) -> tuple[str, str, str]:
    """Повертає (текст з \\n, кодування, стиль переносу рядків)."""
    with open(path, "rb") as f:
        raw = f.read()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    encoding = "utf-8-sig" if raw.startswith(codecs.BOM_UTF8) else "utf-8"
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        encoding = "cp1251"
        text = raw.decode(encoding, errors="replace")
    return text.replace("\r\n", "\n"), encoding, newline


class SmartDecoder:
    """Декодує вивід процесу: спочатку UTF-8, а якщо не вийшло — запасне кодування (OEM на Windows)."""

    def __init__(self, fallback: str):
        self.fallback = fallback
        self._utf8 = codecs.getincrementaldecoder("utf-8")("strict")

    def decode(self, data: bytes, final: bool = False) -> str:
        try:
            return self._utf8.decode(data, final)
        except UnicodeDecodeError:
            self._utf8.reset()
            return data.decode(self.fallback, errors="replace")


def oem_encoding() -> str:
    if os.name == "nt":
        try:
            import ctypes
            name = f"cp{ctypes.windll.kernel32.GetOEMCP()}"
            codecs.lookup(name)
            return name
        except Exception:
            return "cp866"
    return "utf-8"


# ---------------------------------------------------------------------------
# Підсвітка синтаксису
# ---------------------------------------------------------------------------

COMPLETION_NOTE = "Автодоповнення та автозакриття свідомо вимкнені: код вводиться буквально."

_STR_CODE = r"""(?P<string>"(?:\\.|[^"\\\n])*"?|'(?:\\.|[^'\\\n])*'?)"""
_STR_STRICT = r"""(?P<string>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')"""


def _scan_cfg(single: str | None, multiline: list) -> dict:
    return {
        "single": re.compile(single) if single else None,
        "ml": multiline,
        "states": {item[2]: item for item in multiline},
    }


# multiline: (початок, кінець, номер стану блока, вид форматування)
SCAN_CFG = {
    LANG_PY: _scan_cfg(r"(?P<comment>#.*)|" + _STR_CODE,
                       [('"""', '"""', 1, "string"), ("'''", "'''", 2, "string")]),
    LANG_HTML: _scan_cfg(_STR_STRICT, [("<!--", "-->", 5, "comment")]),
    LANG_CSS: _scan_cfg(_STR_STRICT, [("/*", "*/", 3, "comment")]),
    LANG_JS: _scan_cfg(r"(?P<comment>//.*)|" + _STR_CODE,
                       [("/*", "*/", 3, "comment"), ("`", "`", 4, "string")]),
    LANG_CPP: _scan_cfg(r"(?P<comment>//.*)|" + _STR_CODE,
                        [("/*", "*/", 3, "comment")]),
    LANG_TXT: _scan_cfg(_STR_STRICT, []),
}


def make_format(color_hex: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color_hex))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


def _words_re(words) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in sorted(words)) + r")\b")


NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")

PYTHON_KEYWORDS = {
    "def", "class", "return", "if", "elif", "else", "for", "while", "break",
    "continue", "import", "from", "as", "try", "except", "finally", "with",
    "pass", "True", "False", "None", "and", "or", "not", "in", "is", "lambda",
    "async", "await", "yield", "raise", "global", "nonlocal", "del", "assert"
}
PYTHON_BUILTINS = {
    "print", "len", "range", "int", "str", "float", "list", "dict", "set",
    "tuple", "open", "input", "type", "enumerate", "zip", "isinstance", "self"
}
JS_KEYWORDS = {
    "const", "let", "var", "function", "return", "if", "else", "for", "while",
    "switch", "case", "break", "import", "export", "from", "default", "class",
    "new", "try", "catch", "finally", "async", "await", "true", "false", "null",
    "undefined", "this", "continue"
}
CPP_KEYWORDS = {
    "int", "float", "double", "char", "bool", "void", "return", "if", "else",
    "for", "while", "do", "switch", "case", "break", "continue", "class",
    "struct", "public", "private", "protected", "namespace", "using", "include",
    "true", "false", "nullptr", "const", "auto"
}


class UniversalHighlighter(QSyntaxHighlighter):
    """Підсвічувач для Python, HTML, CSS, JS, C++ з підтримкою багаторядкових рядків і коментарів."""

    def __init__(self, document, lang_name: str = LANG_PY):
        super().__init__(document)
        self.lang_name = lang_name

        self.fmt_keyword = make_format("#ff7b72", bold=True)
        self.fmt_builtin = make_format("#d2a8ff")
        self.fmt_string = make_format("#a5d6ff")
        self.fmt_comment = make_format("#8b949e", italic=True)
        self.fmt_number = make_format("#79c0ff")
        self.fmt_tag = make_format("#7ee787", bold=True)
        self.fmt_attr = make_format("#d2a8ff")
        self.fmt_css_prop = make_format("#79c0ff")
        self.fmt_css_val = make_format("#a5d6ff")
        self.fmt_selector = make_format("#ffa657", bold=True)

        # Правила «базового» підсвічування (виконуються до рядків і коментарів,
        # які потім перекривають їх зверху). Усі регулярні вирази скомпільовані один раз.
        self._rules = {
            LANG_PY: [
                (_words_re(PYTHON_KEYWORDS), self.fmt_keyword, 0),
                (_words_re(PYTHON_BUILTINS), self.fmt_builtin, 0),
                (NUMBER_RE, self.fmt_number, 0),
            ],
            LANG_JS: [
                (_words_re(JS_KEYWORDS), self.fmt_keyword, 0),
                (NUMBER_RE, self.fmt_number, 0),
            ],
            LANG_CPP: [
                (_words_re(CPP_KEYWORDS), self.fmt_keyword, 0),
                (re.compile(r"#\s*\w+"), self.fmt_builtin, 0),
                (NUMBER_RE, self.fmt_number, 0),
            ],
            LANG_HTML: [
                (re.compile(r"</?\s*[\w!-]+"), self.fmt_tag, 0),
                (re.compile(r"/?>"), self.fmt_tag, 0),
                (re.compile(r"\b([\w:-]+)\s*="), self.fmt_attr, 1),
            ],
            LANG_CSS: [
                (re.compile(r"([\w-]+)\s*:"), self.fmt_css_prop, 1),
                (re.compile(r":\s*([^;{}]+)"), self.fmt_css_val, 1),
                (re.compile(r"#(?:[0-9a-fA-F]{3,8})\b"), self.fmt_number, 0),
                (re.compile(r"^\s*([^{}/\n]+?)\s*\{"), self.fmt_selector, 1),
            ],
            LANG_TXT: [(NUMBER_RE, self.fmt_number, 0)],
        }

    def set_language(self, lang_name: str):
        self.lang_name = lang_name
        self.rehighlight()

    def _fmt_for(self, kind: str) -> QTextCharFormat:
        return self.fmt_comment if kind == "comment" else self.fmt_string

    def highlightBlock(self, text: str):
        self.setCurrentBlockState(0)
        lang = self.lang_name
        cfg = SCAN_CFG.get(lang, SCAN_CFG[LANG_TXT])
        prev_state = self.previousBlockState()
        n = len(text)

        # 1) Базові правила (ключові слова, числа, теги…).
        if text:
            for regex, fmt, group in self._rules.get(lang, ()):
                for m in regex.finditer(text):
                    start, end = m.span(group)
                    if end > start:
                        self.setFormat(start, end - start, fmt)

        # 2) Рядки та коментарі зліва направо — перший збіг виграє і перекриває базові правила.
        pos = 0
        if prev_state > 0 and prev_state in cfg["states"]:
            _, close, state, kind = cfg["states"][prev_state]
            end = text.find(close)
            if end == -1:
                self.setFormat(0, n, self._fmt_for(kind))
                self.setCurrentBlockState(state)
                return
            pos = end + len(close)
            self.setFormat(0, pos, self._fmt_for(kind))

        single = cfg["single"]
        while pos < n:
            best = None  # (позиція, "single"/"ml", дані)
            if single:
                m = single.search(text, pos)
                if m:
                    best = (m.start(), "single", m)
            for definition in cfg["ml"]:
                i = text.find(definition[0], pos)
                if i != -1 and (best is None or i <= best[0]):
                    best = (i, "ml", definition)
            if best is None:
                break

            if best[1] == "single":
                m = best[2]
                kind = "comment" if m.lastgroup == "comment" else "string"
                self.setFormat(m.start(), m.end() - m.start(), self._fmt_for(kind))
                pos = m.end() if m.end() > pos else pos + 1
            else:
                opener, closer, state, kind = best[2]
                start = best[0]
                end = text.find(closer, start + len(opener))
                if end == -1:
                    self.setFormat(start, n - start, self._fmt_for(kind))
                    self.setCurrentBlockState(state)
                    return
                stop = end + len(closer)
                self.setFormat(start, stop - start, self._fmt_for(kind))
                pos = stop


# ---------------------------------------------------------------------------
# Редактор
# ---------------------------------------------------------------------------

class LineNumberArea(QWidget):
    """Ліва колонка з номерами рядків для EditorTab."""

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


class EditorTab(QPlainTextEdit):
    """Вкладка редактора: номери рядків, підсвітка, відступи. Код вводиться буквально."""

    def __init__(self, lang_name=LANG_PY, file_path=None, content="", font_size=13,
                 encoding="utf-8", newline=None):
        super().__init__()
        self.lang_name = lang_name
        self.file_path = file_path
        self.encoding = encoding
        self.newline = newline or os.linesep
        self.is_modified = False

        self.setFont(mono_font(font_size))
        self.line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.highlighter = UniversalHighlighter(self.document(), self.lang_name)

        self.setPlainText(content)
        self.textChanged.connect(self._on_text_changed)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def set_editor_font_size(self, size: int):
        font = self.font()
        font.setPointSize(size)
        self.setFont(font)
        self.update_line_number_area_width(0)
        self.line_number_area.update()

    def keyPressEvent(self, event):
        """Тільки Tab / Shift+Tab; усе інше вводиться буквально, без автододавання символів."""
        if event.key() == Qt.Key_Tab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                self._indent_selection(unindent=False)
            else:
                cursor.insertText("    ")
            return

        if event.key() == Qt.Key_Backtab:
            self._indent_selection(unindent=True)
            return

        super().keyPressEvent(event)

    def _indent_selection(self, unindent: bool = False):
        cursor = self.textCursor()
        start_block = self.document().findBlock(cursor.selectionStart())
        end_block = self.document().findBlock(cursor.selectionEnd())

        cursor.beginEditBlock()
        block = start_block
        while block.isValid():
            block_cursor = QTextCursor(block)
            if unindent:
                line = block.text()
                if line.startswith("    "):
                    block_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 4)
                    block_cursor.removeSelectedText()
                elif line.startswith("\t"):
                    block_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                    block_cursor.removeSelectedText()
            else:
                block_cursor.insertText("    ")

            if block == end_block:
                break
            block = block.next()
        cursor.endEditBlock()

    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#141720"))

        painter.setPen(QColor("#252a38"))
        painter.drawLine(
            event.rect().right(), event.rect().top(),
            event.rect().right(), event.rect().bottom()
        )

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current_block_number = self.textCursor().blockNumber()

        num_font = QFont(self.font())
        num_font.setPointSize(max(9, self.font().pointSize() - 1))
        painter.setFont(num_font)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#ffffff" if block_number == current_block_number else "#6e7681"))
                painter.drawText(
                    0, top,
                    self.line_number_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignRight | Qt.AlignVCenter,
                    str(block_number + 1)
                )

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#1e2330"))
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def set_language(self, lang_name: str):
        self.lang_name = lang_name
        self.highlighter.set_language(lang_name)

    def _on_text_changed(self):
        self.is_modified = True


class TerminalInput(QLineEdit):
    """Поле вводу команд термінала з історією (стрілки Вгору/Вниз)."""

    def __init__(self, on_submit_callback):
        super().__init__()
        self.on_submit_callback = on_submit_callback
        self.history: list[str] = []
        self.history_index = -1

    def submit(self):
        cmd = self.text().strip()
        if not cmd:
            return
        if not self.history or self.history[-1] != cmd:
            self.history.append(cmd)
        self.history_index = len(self.history)
        self.clear()
        self.on_submit_callback(cmd)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.submit()
            return

        if event.key() == Qt.Key_Up and self.history:
            self.history_index = max(0, self.history_index - 1)
            self.setText(self.history[self.history_index])
            return

        if event.key() == Qt.Key_Down and self.history:
            self.history_index = min(len(self.history), self.history_index + 1)
            if self.history_index == len(self.history):
                self.clear()
            else:
                self.setText(self.history[self.history_index])
            return

        super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Головне вікно
# ---------------------------------------------------------------------------

class CodeEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1240, 740)

        icon_file = resource_path("icon.ico")
        if os.path.exists(icon_file):
            self.setWindowIcon(QIcon(icon_file))

        self.workspace_dir = os.getcwd()
        self.terminal_cwd = self.workspace_dir
        self.editor_font_size = 13

        # Стан запущеного процесу (код або команда термінала).
        self.process: QProcess | None = None
        self._proc_program = ""
        self._cleanup_files: list[str] = []
        self._stopped_by_user = False
        self._dec_out = SmartDecoder(oem_encoding())
        self._dec_err = SmartDecoder(oem_encoding())

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 6)
        main_layout.setSpacing(8)

        # Верхня панель
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.btn_folder = QPushButton("📁 Папка")
        self.btn_folder.setToolTip("Відкрити робочу папку проєкту")

        self.btn_new = QPushButton("+ Вкладка")
        self.btn_new.setToolTip("Створити нову вкладку (Ctrl+N)")

        self.btn_open = QPushButton("📂 Відкрити")
        self.btn_open.setToolTip("Відкрити файл з комп'ютера (Ctrl+O)")

        self.btn_save = QPushButton("💾 Зберегти")
        self.btn_save.setToolTip("Зберегти (Ctrl+S). Зберегти як… — Ctrl+Shift+S")

        self.lang_selector = QComboBox()
        self.lang_selector.addItems(list(LANG_EXTENSIONS.keys()))
        self.lang_selector.setMinimumWidth(155)
        self.lang_selector.setToolTip("Мова програмування або формат файлу")

        self.btn_run = QPushButton("▶ Запустити")
        self.btn_run.setObjectName("runBtn")
        self.btn_run.setToolTip("Запустити код або відкрити HTML у браузері (F5)")

        self.btn_stop = QPushButton("■ Стоп")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setToolTip("Зупинити запущений процес (Ctrl+F2)")
        self.btn_stop.setEnabled(False)

        self.btn_font_down = QPushButton("A-")
        self.btn_font_down.setObjectName("fontBtn")
        self.btn_font_down.setToolTip("Зменшити шрифт коду (Ctrl+-)")

        self.btn_font_up = QPushButton("A+")
        self.btn_font_up.setObjectName("fontBtn")
        self.btn_font_up.setToolTip("Збільшити шрифт коду (Ctrl+=)")

        self.btn_toggle_term = QPushButton("🖥 Термінал")
        self.btn_toggle_term.setCheckable(True)
        self.btn_toggle_term.setChecked(True)
        self.btn_toggle_term.setToolTip("Показати або приховати нижню панель термінала")

        toolbar.addWidget(self.btn_folder)
        toolbar.addWidget(self.btn_new)
        toolbar.addWidget(self.btn_open)
        toolbar.addWidget(self.btn_save)
        toolbar.addWidget(self.lang_selector)
        toolbar.addWidget(self.btn_run)
        toolbar.addWidget(self.btn_stop)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_font_down)
        toolbar.addWidget(self.btn_font_up)
        toolbar.addWidget(self.btn_toggle_term)
        main_layout.addLayout(toolbar)

        h_splitter = QSplitter(Qt.Horizontal)

        # Бічна панель файлів
        sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 4, 0)
        sidebar_layout.setSpacing(6)

        self.sidebar_label = QLabel(os.path.basename(self.workspace_dir) or self.workspace_dir)
        self.sidebar_label.setObjectName("folderTitle")

        sidebar_actions = QHBoxLayout()
        sidebar_actions.setSpacing(4)

        self.btn_create_file = QPushButton("+ Файл")
        self.btn_create_file.setObjectName("miniBtn")
        self.btn_create_file.setToolTip("Створити новий файл")

        self.btn_create_dir = QPushButton("+ Папка")
        self.btn_create_dir.setObjectName("miniBtn")
        self.btn_create_dir.setToolTip("Створити нову папку")

        self.btn_rename_item = QPushButton("✎")
        self.btn_rename_item.setObjectName("iconMiniBtn")
        self.btn_rename_item.setToolTip("Перейменувати виділений елемент")

        self.btn_delete_item = QPushButton("🗑")
        self.btn_delete_item.setObjectName("dangerMiniBtn")
        self.btn_delete_item.setToolTip("Видалити виділений елемент")

        sidebar_actions.addWidget(self.btn_create_file)
        sidebar_actions.addWidget(self.btn_create_dir)
        sidebar_actions.addStretch()
        sidebar_actions.addWidget(self.btn_rename_item)
        sidebar_actions.addWidget(self.btn_delete_item)

        self.file_model = QFileSystemModel(self)
        self.file_model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot | QDir.AllDirs)

        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setIndentation(14)
        for col in range(1, self.file_model.columnCount()):
            self.file_tree.hideColumn(col)

        self.set_workspace_folder(self.workspace_dir)

        sidebar_layout.addWidget(self.sidebar_label)
        sidebar_layout.addLayout(sidebar_actions)
        sidebar_layout.addWidget(self.file_tree)
        h_splitter.addWidget(sidebar_container)

        # Центр: редактор + термінал
        self.v_splitter = QSplitter(Qt.Vertical)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.v_splitter.addWidget(self.tabs)

        self.console_container = QWidget()
        console_layout = QVBoxLayout(self.console_container)
        console_layout.setContentsMargins(0, 4, 0, 0)
        console_layout.setSpacing(5)

        console_top = QHBoxLayout()
        self.console_label = QLabel(f"Термінал • {self.terminal_cwd}")
        self.btn_clear = QPushButton("Очистити")
        self.btn_clear.setObjectName("ghostBtn")
        self.btn_clear.setToolTip("Очистити вивід термінала")
        console_top.addWidget(self.console_label)
        console_top.addStretch()
        console_top.addWidget(self.btn_clear)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(mono_font(11))
        self.console.setObjectName("console")

        cmd_row = QHBoxLayout()
        self.prompt_badge = QLabel(">")
        self.prompt_badge.setObjectName("promptBadge")
        self.terminal_input = TerminalInput(self.run_terminal_command)
        self.terminal_input.setFont(mono_font(11))
        self.terminal_input.setPlaceholderText(
            "Команда + Enter (напр.: python --version або cls). Якщо програма чекає input() — пиши відповідь сюди."
        )
        self.terminal_input.setObjectName("termInput")

        self.btn_exec_cmd = QPushButton("Виконати")
        self.btn_exec_cmd.setObjectName("execBtn")

        cmd_row.addWidget(self.prompt_badge)
        cmd_row.addWidget(self.terminal_input)
        cmd_row.addWidget(self.btn_exec_cmd)

        console_layout.addLayout(console_top)
        console_layout.addWidget(self.console)
        console_layout.addLayout(cmd_row)
        self.v_splitter.addWidget(self.console_container)

        self.v_splitter.setSizes([520, 165])
        h_splitter.addWidget(self.v_splitter)
        h_splitter.setSizes([240, 980])

        main_layout.addWidget(h_splitter)

        # Рядок стану
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_enc_label = QLabel("")
        self.status_enc_label.setObjectName("statusHint")
        self.status_hint_label = QLabel(self._status_hint())
        self.status_hint_label.setObjectName("statusHint")
        self.status_bar.addPermanentWidget(self.status_enc_label)
        self.status_bar.addPermanentWidget(self.status_hint_label)

        # Сигнали
        self.btn_folder.clicked.connect(self.choose_folder)
        self.btn_create_file.clicked.connect(self.create_file_in_sidebar)
        self.btn_create_dir.clicked.connect(self.create_folder_in_sidebar)
        self.btn_rename_item.clicked.connect(self.rename_selected_item)
        self.btn_delete_item.clicked.connect(self.delete_selected_item)
        self.btn_new.clicked.connect(self.create_new_tab)
        self.btn_open.clicked.connect(self.open_file)
        self.btn_save.clicked.connect(self.save_file)
        self.btn_run.clicked.connect(self.run_code)
        self.btn_stop.clicked.connect(self.stop_process)
        self.btn_font_down.clicked.connect(lambda: self.change_font_size(-1))
        self.btn_font_up.clicked.connect(lambda: self.change_font_size(1))
        self.btn_clear.clicked.connect(self.console.clear)
        self.btn_toggle_term.toggled.connect(self.toggle_terminal)
        self.btn_exec_cmd.clicked.connect(self.terminal_input.submit)
        self.lang_selector.currentTextChanged.connect(self.on_language_changed)

        self.file_tree.doubleClicked.connect(self.on_tree_double_clicked)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        QShortcut(QKeySequence("F5"), self).activated.connect(self.run_code)
        QShortcut(QKeySequence("Ctrl+F2"), self).activated.connect(self.stop_process)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_file)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.save_file_as)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_file)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.create_new_tab)
        QShortcut(QKeySequence("Ctrl+="), self).activated.connect(lambda: self.change_font_size(1))
        QShortcut(QKeySequence("Ctrl++"), self).activated.connect(lambda: self.change_font_size(1))
        QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(lambda: self.change_font_size(-1))
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(
            lambda: self.close_tab(self.tabs.currentIndex())
        )

        self.apply_styles()
        self.create_new_tab()
        self.open_workspace_files()

    # ------------------------------------------------------------------ UI

    def _status_hint(self) -> str:
        return (f"Шрифт: {self.editor_font_size} pt   •   F5 — Запуск   •   "
                f"Ctrl+S — Зберегти   •   Ctrl+N — Нова вкладка")

    def change_font_size(self, delta: int):
        new_size = max(9, min(32, self.editor_font_size + delta))
        if new_size == self.editor_font_size:
            return
        self.editor_font_size = new_size
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, EditorTab):
                tab.set_editor_font_size(self.editor_font_size)
        self.status_hint_label.setText(self._status_hint())

    def toggle_terminal(self, visible: bool):
        self.console_container.setVisible(visible)
        if visible:
            self.v_splitter.setSizes([520, 165])

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #12141a;
                color: #e4e6eb;
                font-family: 'Segoe UI', sans-serif;
            }
            QPushButton, QComboBox {
                background-color: #1c202b;
                color: #f0f2f5;
                border: 1px solid #2c3244;
                border-radius: 7px;
                padding: 7px 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover, QComboBox:hover {
                background-color: #252b3a;
                border-color: #465275;
            }
            QPushButton:disabled {
                color: #5b6270;
                background-color: #171a22;
                border-color: #232838;
            }
            QPushButton:checked {
                background-color: #222b3d;
                border-color: #388bfd;
                color: #ffffff;
            }
            QPushButton#fontBtn {
                padding: 7px 10px;
                min-width: 34px;
                font-weight: 700;
            }
            QPushButton#miniBtn {
                padding: 5px 9px;
                font-size: 12px;
                border-radius: 6px;
            }
            QPushButton#iconMiniBtn {
                padding: 5px 8px;
                font-size: 12px;
                border-radius: 6px;
            }
            QPushButton#dangerMiniBtn {
                background-color: #261417;
                color: #ff7b72;
                border: 1px solid #4d2228;
                padding: 5px 8px;
                font-size: 12px;
                border-radius: 6px;
            }
            QPushButton#dangerMiniBtn:hover {
                background-color: #3d1b20;
                border-color: #f85149;
            }
            QPushButton#ghostBtn {
                background-color: transparent;
                border: 1px solid #282d3d;
                color: #9da5b4;
                padding: 3px 9px;
                font-size: 11px;
                border-radius: 5px;
            }
            QPushButton#ghostBtn:hover {
                background-color: #1c202b;
                color: #ffffff;
            }
            QPushButton#runBtn {
                background-color: #1f6feb;
                border-color: #388bfd;
                color: #ffffff;
                padding: 7px 14px;
            }
            QPushButton#runBtn:hover {
                background-color: #388bfd;
            }
            QPushButton#stopBtn {
                background-color: #3d1b20;
                border-color: #f85149;
                color: #ffb3ad;
                padding: 7px 14px;
            }
            QPushButton#stopBtn:hover {
                background-color: #5a2128;
            }
            QPushButton#stopBtn:disabled {
                background-color: #171a22;
                border-color: #232838;
                color: #5b6270;
            }
            QPushButton#execBtn {
                background-color: #238636;
                border-color: #2ea043;
                color: #ffffff;
                padding: 6px 12px;
            }
            QPushButton#execBtn:hover {
                background-color: #2ea043;
            }
            QTreeView {
                background-color: #151821;
                color: #d0d7de;
                border: 1px solid #252a38;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
                outline: none;
            }
            QTreeView::item {
                padding: 5px 6px;
                border-radius: 5px;
            }
            QTreeView::item:hover {
                background-color: #1f2433;
            }
            QTreeView::item:selected {
                background-color: #264f78;
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #252a38;
                border-radius: 8px;
                background-color: #171a22;
            }
            QTabBar::tab {
                background-color: #141720;
                color: #8b949e;
                border: 1px solid #252a38;
                border-bottom: none;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                padding: 7px 14px;
                margin-right: 3px;
                font-size: 13px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #171a22;
                color: #ffffff;
                border-top: 2px solid #388bfd;
            }
            QTabBar::tab:hover:!selected {
                background-color: #1d212e;
                color: #c9d1d9;
            }
            QPlainTextEdit {
                background-color: #171a22;
                color: #f8f8f2;
                border: none;
                border-radius: 8px;
                padding: 10px;
                selection-background-color: #264f78;
            }
            QPlainTextEdit#console {
                background-color: #0d0f14;
                color: #7ee787;
                border: 1px solid #222634;
                border-radius: 7px;
            }
            QLineEdit#termInput {
                background-color: #0d0f14;
                color: #ffffff;
                border: 1px solid #252a38;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QLineEdit#termInput:focus {
                border-color: #388bfd;
            }
            QLabel {
                color: #8b949e;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#folderTitle {
                color: #c9d1d9;
                font-size: 13px;
                font-weight: 700;
                padding-left: 2px;
            }
            QLabel#promptBadge {
                color: #7ee787;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px;
                padding: 0 2px;
            }
            QLabel#statusHint {
                color: #7d8590;
                font-size: 12px;
                padding-right: 8px;
            }
            QStatusBar {
                background-color: #101218;
                border-top: 1px solid #202430;
            }
        """)

    # --------------------------------------------- Операції з файлами в дереві

    def _selected_item_path(self) -> str | None:
        index = self.file_tree.currentIndex()
        if not index.isValid():
            return None
        path = os.path.abspath(self.file_model.filePath(index))
        return path if os.path.exists(path) else None

    def _target_directory_for_creation(self) -> str:
        selected_path = self._selected_item_path()
        if selected_path:
            if os.path.isdir(selected_path):
                return selected_path
            if os.path.isfile(selected_path):
                return os.path.dirname(selected_path)
        return os.path.abspath(self.workspace_dir)

    def _update_open_tabs_after_rename(self, old_path: str, new_path: str):
        old_abs = os.path.abspath(old_path)
        new_abs = os.path.abspath(new_path)
        old_norm = norm(old_abs)

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if not isinstance(tab, EditorTab) or not tab.file_path:
                continue
            tab_abs = os.path.abspath(tab.file_path)

            if norm(tab_abs) == old_norm:
                tab.file_path = new_abs
                lang = detect_language(new_abs)
                if lang:
                    tab.set_language(lang)
                    if i == self.tabs.currentIndex():
                        self.lang_selector.blockSignals(True)
                        self.lang_selector.setCurrentText(lang)
                        self.lang_selector.blockSignals(False)
                self.update_tab_title(i)
            elif norm(tab_abs).startswith(old_norm + os.sep):
                rel = tab_abs[len(old_abs) + 1:]
                tab.file_path = os.path.join(new_abs, rel)
                self.update_tab_title(i)

    def _close_open_tabs_for_deleted_path(self, deleted_path: str):
        for i in range(self.tabs.count() - 1, -1, -1):
            tab = self.tabs.widget(i)
            if not isinstance(tab, EditorTab) or not tab.file_path:
                continue
            if path_inside(tab.file_path, deleted_path):
                tab.is_modified = False
                self.tabs.removeTab(i)

        if self.tabs.count() == 0:
            self.create_new_tab()

    def rename_selected_item(self):
        target_path = self._selected_item_path()
        if not target_path:
            QMessageBox.information(self, "Перейменування", "Спочатку вибери файл або папку у списку зліва.")
            return

        old_name = os.path.basename(target_path)
        parent_dir = os.path.dirname(target_path)
        new_name, ok = QInputDialog.getText(
            self, "Перейменувати", f"Нова назва для «{old_name}»:", text=old_name
        )
        if not ok or not new_name.strip():
            return

        clean_new_name = new_name.strip()
        if clean_new_name == old_name:
            return
        if any(sep in clean_new_name for sep in ("/", "\\")):
            QMessageBox.warning(self, "Некоректна назва", "Назва не може містити / або \\.")
            return

        new_path = os.path.abspath(os.path.join(parent_dir, clean_new_name))
        if os.path.exists(new_path) and norm(new_path) != norm(target_path):
            QMessageBox.warning(self, "Назва зайнята", f"Об'єкт «{clean_new_name}» уже існує.")
            return

        try:
            os.rename(target_path, new_path)
            self._update_open_tabs_after_rename(target_path, new_path)
            self.status_bar.showMessage(f"Перейменовано в «{clean_new_name}»", 3000)
        except OSError as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося перейменувати:\n{e}")

    def delete_selected_item(self):
        target_path = self._selected_item_path()
        if not target_path:
            QMessageBox.information(self, "Видалення", "Спочатку вибери файл або папку у списку зліва.")
            return

        if norm(target_path) == norm(self.workspace_dir) or not path_inside(target_path, self.workspace_dir):
            QMessageBox.warning(self, "Видалення заборонено",
                                "Кореневу робочу папку та елементи поза нею видаляти не можна.")
            return

        item_name = os.path.basename(target_path)
        is_dir = os.path.isdir(target_path)
        kind_label = "папку з усім вмістом" if is_dir else "файл"
        where = "У кошик" if send2trash else "НАЗАВЖДИ (кошик недоступний: pip install send2trash)"

        reply = QMessageBox.question(
            self, "Видалити?",
            f"Видалити {kind_label} «{item_name}»?\n\nКуди: {where}.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            if send2trash:
                send2trash(target_path)
            elif is_dir:
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)

            self._close_open_tabs_for_deleted_path(target_path)
            self.status_bar.showMessage(f"Видалено «{item_name}»", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося видалити:\n{e}")

    def create_file_in_sidebar(self):
        target_dir = self._target_directory_for_creation()
        file_name, ok = QInputDialog.getText(
            self, "Новий файл", "Ім'я файлу (наприклад: index.html, style.css, app.py):"
        )
        if not ok or not file_name.strip():
            return

        clean_name = file_name.strip()
        new_file_path = os.path.abspath(os.path.join(target_dir, clean_name))
        if not path_inside(new_file_path, self.workspace_dir):
            QMessageBox.warning(self, "Некоректний шлях", "Файл має бути всередині робочої папки.")
            return

        try:
            os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
            if not os.path.exists(new_file_path):
                with open(new_file_path, "w", encoding="utf-8"):
                    pass
                self.status_bar.showMessage(f"Створено файл {clean_name}", 3000)
            self.open_paths_in_tabs([new_file_path])
        except OSError as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити файл:\n{e}")

    def create_folder_in_sidebar(self):
        target_dir = self._target_directory_for_creation()
        folder_name, ok = QInputDialog.getText(self, "Нова папка", "Назва нової папки:")
        if not ok or not folder_name.strip():
            return

        new_folder_path = os.path.abspath(os.path.join(target_dir, folder_name.strip()))
        if not path_inside(new_folder_path, self.workspace_dir):
            QMessageBox.warning(self, "Некоректний шлях", "Папка має бути всередині робочої папки.")
            return
        try:
            os.makedirs(new_folder_path, exist_ok=True)
            self.status_bar.showMessage(f"Створено папку {folder_name.strip()}", 3000)
        except OSError as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити папку:\n{e}")

    def set_workspace_folder(self, folder_path: str):
        if folder_path and os.path.isdir(folder_path):
            abs_folder = os.path.abspath(folder_path)
            self.workspace_dir = abs_folder
            root_idx = self.file_model.setRootPath(abs_folder)
            self.file_tree.setRootIndex(root_idx)
            self.sidebar_label.setText(os.path.basename(abs_folder) or abs_folder)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Обрати папку проєкту", self.workspace_dir)
        if folder:
            self.set_workspace_folder(folder)
            self._set_terminal_cwd(os.path.abspath(folder))
            self.open_workspace_files()

    def _set_terminal_cwd(self, path: str):
        self.terminal_cwd = path
        self.console_label.setText(f"Термінал • {self.terminal_cwd}")

    def collect_workspace_text_files(self):
        """Знаходить текстові файли проєкту, пропускаючи службові та дуже великі файли."""
        root = os.path.abspath(self.workspace_dir)
        found = []

        for current_dir, dir_names, file_names in os.walk(root, followlinks=False):
            dir_names[:] = sorted(
                name for name in dir_names
                if name.lower() not in PROJECT_IGNORED_DIRS
                and not os.path.islink(os.path.join(current_dir, name))
            )

            for file_name in file_names:
                full_path = os.path.join(current_dir, file_name)
                if os.path.islink(full_path) or not os.path.isfile(full_path):
                    continue

                extension = os.path.splitext(file_name)[1].lower()
                if extension not in PROJECT_TEXT_EXTENSIONS and file_name.lower() not in PROJECT_TEXT_FILENAMES:
                    continue

                try:
                    if os.path.getsize(full_path) > MAX_PROJECT_TEXT_FILE_SIZE:
                        continue
                except OSError:
                    continue

                found.append(os.path.abspath(full_path))

        return sorted(found, key=lambda path: os.path.relpath(path, root).lower())

    def open_workspace_files(self):
        """Відкриває текстові файли робочої папки (не більше MAX_AUTO_OPEN_FILES)."""
        paths = self.collect_workspace_text_files()
        if not paths:
            self.status_bar.showMessage("У папці проєкту не знайдено підтримуваних текстових файлів", 5000)
            return

        to_open = paths[:MAX_AUTO_OPEN_FILES]
        self.open_paths_in_tabs(to_open, sync_cwd=False)
        if len(paths) > len(to_open):
            self.status_bar.showMessage(
                f"Відкрито {len(to_open)} із {len(paths)} файлів. Решту відкривай подвійним кліком у дереві.",
                8000
            )
        else:
            self.status_bar.showMessage(f"Відкрито файлів проєкту: {len(to_open)}", 5000)

    def on_tree_double_clicked(self, index: QModelIndex):
        if not index.isValid():
            return
        file_path = self.file_model.filePath(index)
        if os.path.isfile(file_path):
            self.open_paths_in_tabs([file_path])

    # ---------------------------------------------------------------- Термінал

    def console_write(self, text: str):
        self.console.moveCursor(QTextCursor.End)
        self.console.insertPlainText(text)
        self.console.moveCursor(QTextCursor.End)
        self.console.ensureCursorVisible()

    def sync_terminal_cwd_with_editor(self):
        """Терміналу вистачає папки поточного файлу; дерево файлів при цьому не перемикається."""
        editor = self.current_editor()
        if editor and editor.file_path:
            folder = os.path.dirname(os.path.abspath(editor.file_path))
            if os.path.isdir(folder):
                self._set_terminal_cwd(folder)

    def is_running(self) -> bool:
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def _start_process(self, program: str, args: list[str] | None = None,
                       native_args: str | None = None, cleanup: list[str] | None = None) -> bool:
        if self.is_running():
            self.console_write("[Інфо]: Уже виконується процес. Дочекайся завершення або натисни ■ Стоп.\n")
            return False

        proc = QProcess(self)
        proc.setWorkingDirectory(self.terminal_cwd)

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUTF8", "1")
        env.insert("PYTHONUNBUFFERED", "1")
        proc.setProcessEnvironment(env)

        self._dec_out = SmartDecoder(oem_encoding())
        self._dec_err = SmartDecoder(oem_encoding())
        self._cleanup_files = list(cleanup or [])
        self._proc_program = program
        self._stopped_by_user = False

        proc.readyReadStandardOutput.connect(lambda: self._read_output(False))
        proc.readyReadStandardError.connect(lambda: self._read_output(True))
        proc.finished.connect(self._on_process_finished)
        proc.errorOccurred.connect(self._on_process_error)

        self.process = proc
        self.btn_stop.setEnabled(True)

        proc.setProgram(program)
        if native_args is not None and hasattr(proc, "setNativeArguments"):
            proc.setNativeArguments(native_args)
        else:
            proc.setArguments(args or [])
        proc.start()
        return True

    def _read_output(self, is_err: bool):
        proc = self.process
        if proc is None:
            return
        if is_err:
            data = proc.readAllStandardError().data()
            self.console_write(self._dec_err.decode(data))
        else:
            data = proc.readAllStandardOutput().data()
            self.console_write(self._dec_out.decode(data))

    def _on_process_finished(self, exit_code: int, exit_status):
        self._read_output(False)
        self._read_output(True)
        self.console_write(self._dec_out.decode(b"", True) + self._dec_err.decode(b"", True))

        if self._stopped_by_user:
            self.console_write("\n[Зупинено користувачем]\n")
        elif exit_status == QProcess.CrashExit:
            self.console_write("\n[Процес аварійно завершився]\n")
        else:
            self.console_write(f"\n[Завершено, код {exit_code}]\n")
        self._cleanup_process()

    def _on_process_error(self, error):
        if error == QProcess.FailedToStart:
            name = os.path.basename(self._proc_program).lower()
            if name.startswith("node"):
                self.console_write("[Інфо]: Для запуску .js потрібен встановлений Node.js.\n")
            else:
                self.console_write(f"[Помилка]: не вдалося запустити «{self._proc_program}».\n")
            self._cleanup_process()

    def _cleanup_process(self):
        for path in self._cleanup_files:
            self._remove_quietly(path)
        self._cleanup_files = []
        if self.process is not None:
            self.process.deleteLater()
            self.process = None
        self.btn_stop.setEnabled(False)

    @staticmethod
    def _remove_quietly(path: str):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    def stop_process(self):
        if self.is_running():
            self._stopped_by_user = True
            self.process.kill()

    def run_terminal_command(self, cmd: str):
        # Якщо процес чекає введення (наприклад, input()), відправляємо рядок у його stdin.
        if self.is_running():
            self.process.write((cmd + "\n").encode("utf-8"))
            self.console_write(f"{cmd}\n")
            return

        self.console_write(f"> {cmd}\n")

        if cmd.lower() in ("cls", "clear"):
            self.console.clear()
            return

        if cmd.lower() == "cd" or cmd.lower().startswith("cd "):
            target = cmd[2:].strip()
            if target.lower().startswith("/d "):
                target = target[3:].strip()
            target = os.path.expanduser(target.strip('"').strip("'"))
            if not target:
                self.console_write(self.terminal_cwd + "\n")
                return
            new_path = os.path.abspath(os.path.join(self.terminal_cwd, target))
            if os.path.isdir(new_path):
                self._set_terminal_cwd(new_path)
            else:
                self.console_write(f"Шлях не знайдено: {new_path}\n")
            return

        if os.name == "nt":
            self._start_process("cmd.exe", native_args=f'/d /s /c "{cmd}"')
        else:
            self._start_process("/bin/sh", ["-c", cmd])

    # ------------------------------------------------------------- Вкладки

    def current_editor(self) -> EditorTab | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, EditorTab) else None

    def _refresh_status_encoding(self):
        editor = self.current_editor()
        if editor:
            nl = "CRLF" if editor.newline == "\r\n" else "LF"
            self.status_enc_label.setText(f"{editor.encoding.upper()}  •  {nl}")
        else:
            self.status_enc_label.setText("")

    def update_tab_title(self, index: int):
        editor = self.tabs.widget(index)
        if not isinstance(editor, EditorTab):
            return
        if editor.file_path:
            name = os.path.basename(editor.file_path)
        else:
            name = f"новий{LANG_EXTENSIONS.get(editor.lang_name, '.txt')}"

        if editor.is_modified:
            name += " *"
        self.tabs.setTabText(index, name)

        if index == self.tabs.currentIndex():
            title_path = editor.file_path if editor.file_path else name
            self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — {title_path}")
            self._refresh_status_encoding()

    def create_new_tab(self, checked=False, lang_name=None, file_path=None, content="",
                       encoding="utf-8", newline=None):
        if lang_name is None:
            lang_name = self.lang_selector.currentText()

        editor = EditorTab(
            lang_name=lang_name,
            file_path=file_path,
            content=content or "",
            font_size=self.editor_font_size,
            encoding=encoding,
            newline=newline,
        )
        editor.is_modified = False

        index = self.tabs.addTab(editor, "")
        editor.textChanged.connect(lambda ed=editor: self.update_tab_title(self.tabs.indexOf(ed)))

        self.tabs.setCurrentIndex(index)
        self.update_tab_title(index)

    def maybe_save(self, editor: EditorTab) -> bool:
        """Питає про збереження змін. Повертає False, якщо користувач натиснув «Скасувати»."""
        if not editor.is_modified:
            return True
        name = os.path.basename(editor.file_path) if editor.file_path else "новий файл"
        box = QMessageBox.question(
            self, "Незбережені зміни", f"Зберегти зміни у «{name}»?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save
        )
        if box == QMessageBox.Save:
            return self.save_editor(editor)
        return box == QMessageBox.Discard

    def close_tab(self, index: int):
        if index < 0:
            return
        editor = self.tabs.widget(index)
        if isinstance(editor, EditorTab):
            self.tabs.setCurrentIndex(index)
            if not self.maybe_save(editor):
                return

        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.create_new_tab()

    def closeEvent(self, event):
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, EditorTab) and editor.is_modified:
                self.tabs.setCurrentIndex(i)
                if not self.maybe_save(editor):
                    event.ignore()
                    return

        if self.is_running():
            self._stopped_by_user = True
            self.process.kill()
            self.process.waitForFinished(1000)
        for path in self._cleanup_files:
            self._remove_quietly(path)
        event.accept()

    def on_tab_changed(self, index: int):
        editor = self.current_editor()
        if editor:
            self.lang_selector.blockSignals(True)
            self.lang_selector.setCurrentText(editor.lang_name)
            self.lang_selector.blockSignals(False)
            self.update_tab_title(index)
        else:
            self._refresh_status_encoding()

    def on_language_changed(self, lang_name: str):
        editor = self.current_editor()
        if not editor:
            return
        editor.set_language(lang_name)
        self.update_tab_title(self.tabs.currentIndex())

    # ------------------------------------------------------ Відкриття / збереження

    def open_paths_in_tabs(self, paths, sync_cwd: bool = True):
        for path in paths:
            abs_path = os.path.abspath(path)

            already_open = False
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if isinstance(tab, EditorTab) and tab.file_path and norm(tab.file_path) == norm(abs_path):
                    self.tabs.setCurrentIndex(i)
                    already_open = True
                    break
            if already_open:
                continue

            try:
                content, encoding, newline = read_text_file(abs_path)
            except OSError as e:
                QMessageBox.warning(self, "Не вдалося відкрити", f"{abs_path}\n\n{e}")
                continue

            detected_lang = detect_language(abs_path) or LANG_TXT

            curr = self.current_editor()
            if (
                self.tabs.count() == 1
                and curr is not None
                and not curr.file_path
                and not curr.is_modified
            ):
                curr.file_path = abs_path
                curr.encoding = encoding
                curr.newline = newline
                curr.set_language(detected_lang)
                curr.blockSignals(True)
                curr.setPlainText(content)
                curr.blockSignals(False)
                curr.is_modified = False
                self.lang_selector.blockSignals(True)
                self.lang_selector.setCurrentText(detected_lang)
                self.lang_selector.blockSignals(False)
                self.update_tab_title(0)
            else:
                self.create_new_tab(lang_name=detected_lang, file_path=abs_path,
                                    content=content, encoding=encoding, newline=newline)

        if sync_cwd:
            self.sync_terminal_cwd_with_editor()

    def open_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Відкрити файли", self.terminal_cwd,
            "Усі підтримувані файли (*.py *.html *.css *.js *.cpp *.c *.json *.txt);;Усі файли (*)"
        )
        if paths:
            self.open_paths_in_tabs(paths)

    def save_editor(self, editor: EditorTab, save_as: bool = False) -> bool:
        """Зберігає вкладку. Повертає True, якщо файл збережено."""
        path = editor.file_path

        if save_as or not path:
            default_ext = LANG_EXTENSIONS.get(editor.lang_name, ".txt")
            default_name = {".html": "index.html", ".css": "style.css"}.get(default_ext, f"main{default_ext}")
            start = path or os.path.join(self.terminal_cwd, default_name)
            chosen, _ = QFileDialog.getSaveFileName(self, "Зберегти файл", start, "Усі файли (*)")
            if not chosen:
                return False
            path = os.path.abspath(chosen)

        text = editor.toPlainText().replace("\n", editor.newline)
        encoding = editor.encoding
        try:
            try:
                data = text.encode(encoding)
            except UnicodeEncodeError:
                reply = QMessageBox.question(
                    self, "Кодування",
                    f"Кодування {encoding.upper()} не підтримує всі символи в тексті.\n"
                    f"Зберегти у UTF-8?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                if reply != QMessageBox.Yes:
                    return False
                encoding = "utf-8"
                data = text.encode(encoding)

            with open(path, "wb") as f:
                f.write(data)
        except OSError as e:
            QMessageBox.critical(self, "Помилка збереження", f"Не вдалося зберегти файл:\n{e}")
            return False

        editor.encoding = encoding
        editor.file_path = path
        editor.is_modified = False

        if save_as:
            lang = detect_language(path)
            if lang and lang != editor.lang_name:
                editor.set_language(lang)
                if editor is self.current_editor():
                    self.lang_selector.blockSignals(True)
                    self.lang_selector.setCurrentText(lang)
                    self.lang_selector.blockSignals(False)

        self.update_tab_title(self.tabs.indexOf(editor))
        self.sync_terminal_cwd_with_editor()
        self.status_bar.showMessage(f"Збережено: {os.path.basename(path)}", 3000)
        return True

    def save_file(self):
        editor = self.current_editor()
        if editor:
            self.save_editor(editor)

    def save_file_as(self):
        editor = self.current_editor()
        if editor:
            self.save_editor(editor, save_as=True)

    # --------------------------------------------------------------- Запуск

    @staticmethod
    def python_executable() -> str:
        if getattr(sys, "frozen", False):
            return shutil.which("python") or shutil.which("py") or shutil.which("python3") or "python"
        return sys.executable

    def run_code(self):
        editor = self.current_editor()
        if not editor:
            return

        code = editor.toPlainText()
        if not code.strip():
            return

        ext = LANG_EXTENSIONS.get(editor.lang_name, ".txt")
        self.console_container.setVisible(True)
        self.btn_toggle_term.setChecked(True)

        if ext in (".py", ".js") and self.is_running():
            self.console_write("[Інфо]: Уже виконується процес. Дочекайся завершення або натисни ■ Стоп.\n")
            return

        self.console.clear()

        if ext in (".py", ".js"):
            cleanup: list[str] = []
            if editor.file_path:
                # Є файл на диску — зберігаємо і запускаємо його самого (працюють __file__ та імпорти поруч).
                if editor.is_modified or not os.path.exists(editor.file_path):
                    if not self.save_editor(editor):
                        return
                script_path = editor.file_path
            else:
                with tempfile.NamedTemporaryFile("w", suffix=ext, delete=False, encoding="utf-8") as tmp:
                    tmp.write(code)
                    script_path = tmp.name
                cleanup.append(script_path)

            self.console_write(f"▶ Запуск: {os.path.basename(editor.file_path or script_path)}\n\n")
            if ext == ".py":
                self._start_process(self.python_executable(), ["-u", script_path], cleanup=cleanup)
            else:
                self._start_process("node", [script_path], cleanup=cleanup)

        elif ext == ".html":
            if editor.file_path:
                if editor.is_modified and not self.save_editor(editor):
                    return
                webbrowser.open(Path(editor.file_path).resolve().as_uri())
                self.console_write(f"[Відкрито у браузері]: {editor.file_path}\n")
            else:
                with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tmp:
                    tmp.write(code)
                    tmp_path = tmp.name
                webbrowser.open(Path(tmp_path).resolve().as_uri())
                # Тимчасовий файл видаляємо трохи пізніше, коли браузер уже встиг його прочитати.
                QTimer.singleShot(60_000, lambda p=tmp_path: self._remove_quietly(p))
                self.console_write("[Відкрито тимчасовий HTML у браузері]\n")

        else:
            self.console_write(
                f"[Інфо]: Файл {ext} готовий. Відкрий вкладку HTML і натисни F5 для перегляду в браузері.\n"
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CodeEditor()
    window.show()
    sys.exit(app.exec())
