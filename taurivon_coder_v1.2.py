import sys
import subprocess
import tempfile
import os
import re
import shutil
import webbrowser
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QPushButton, QFileDialog, QSplitter, QLabel,
    QComboBox, QTabWidget, QMessageBox, QTextEdit, QLineEdit, QCompleter,
    QTreeView, QFileSystemModel, QInputDialog, QStatusBar
)
from PySide6.QtGui import (
    QFont, QKeySequence, QShortcut, QSyntaxHighlighter, QTextCharFormat,
    QColor, QPainter, QTextFormat, QTextCursor, QIcon
)
from PySide6.QtCore import Qt, QRect, QSize, QStringListModel, QDir, QModelIndex


APP_NAME = "TAURIVON Coder"
APP_VERSION = "1.2"


def resource_path(relative_path: str) -> str:
    """Повертає коректний шлях до ресурсів як у Python, так і всередині зібраного .exe."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


LANG_EXTENSIONS = {
    "Python (.py)": ".py",
    "HTML (.html)": ".html",
    "CSS (.css)": ".css",
    "JavaScript (.js)": ".js",
    "C++ (.cpp)": ".cpp",
    "Текст (.txt)": ".txt"
}


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
MAX_PROJECT_TEXT_FILE_SIZE = 2 * 1024 * 1024  # Не завантажуємо в редактор файли понад 2 МБ.


COMPLETION_WORDS = {
    "Python (.py)": sorted({
        "def", "class", "return", "if", "elif", "else", "for", "while", "break",
        "continue", "import", "from", "as", "try", "except", "finally", "with",
        "pass", "True", "False", "None", "and", "or", "not", "in", "is", "lambda",
        "async", "await", "yield", "print", "len", "range", "int", "str", "float",
        "list", "dict", "set", "tuple", "open", "input", "type", "enumerate",
        "zip", "isinstance", "__init__", "self"
    }),
    "HTML (.html)": sorted([
        "!DOCTYPE", "html", "head", "meta", "title", "link", "script", "style",
        "body", "header", "nav", "main", "section", "article", "footer",
        "div", "span", "p", "a", "h1", "h2", "h3", "ul", "ol", "li",
        "button", "input", "form", "label", "img", "table", "tr", "td", "th"
    ]),
    "CSS (.css)": sorted([
        "background", "background-color", "color", "font-size", "font-family",
        "font-weight", "margin", "margin-top", "margin-bottom", "padding",
        "border", "border-radius", "display", "flex", "grid", "align-items",
        "justify-content", "gap", "width", "height", "max-width", "position",
        "hover", "active", "cursor", "pointer", "box-shadow", "transition"
    ]),
    "JavaScript (.js)": sorted([
        "const", "let", "var", "function", "return", "if", "else", "for", "while",
        "switch", "case", "break", "import", "export", "from", "default", "class",
        "new", "try", "catch", "finally", "async", "await", "true", "false",
        "null", "undefined", "console.log", "document", "window", "addEventListener",
        "querySelector"
    ]),
    "C++ (.cpp)": sorted([
        "#include", "<iostream>", "<vector>", "<string>", "int", "float",
        "double", "char", "bool", "void", "return", "if", "else", "for",
        "while", "do", "switch", "case", "break", "continue", "class", "struct",
        "public", "private", "protected", "namespace", "std", "cout", "cin",
        "endl", "true", "false", "nullptr", "const"
    ]),
    "Текст (.txt)": []
}


def make_format(color_hex: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color_hex))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class UniversalHighlighter(QSyntaxHighlighter):
    """Підсвічувач синтаксису для Python, HTML, CSS, JS, C++ та загального коду."""

    PYTHON_KEYWORDS = {
        "def", "class", "return", "if", "elif", "else", "for", "while", "break",
        "continue", "import", "from", "as", "try", "except", "finally", "with",
        "pass", "True", "False", "None", "and", "or", "not", "in", "is", "lambda",
        "async", "await", "yield"
    }
    PYTHON_BUILTINS = {
        "print", "len", "range", "int", "str", "float", "list", "dict", "set",
        "tuple", "open", "input", "type", "enumerate", "zip", "isinstance"
    }
    JS_KEYWORDS = {
        "const", "let", "var", "function", "return", "if", "else", "for", "while",
        "switch", "case", "break", "import", "export", "from", "default", "class",
        "new", "try", "catch", "finally", "async", "await", "true", "false", "null",
        "undefined"
    }
    CPP_KEYWORDS = {
        "int", "float", "double", "char", "bool", "void", "return", "if", "else",
        "for", "while", "do", "switch", "case", "break", "continue", "class",
        "struct", "public", "private", "protected", "namespace", "using", "include",
        "true", "false", "nullptr", "const"
    }

    def __init__(self, document, lang_name: str = "Python (.py)"):
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

    def set_language(self, lang_name: str):
        self.lang_name = lang_name
        self.rehighlight()

    def _highlight_words(self, text: str, words: set, fmt: QTextCharFormat):
        if not words:
            return
        pattern = r"\b(" + "|".join(re.escape(w) for w in words) + r")\b"
        for match in re.finditer(pattern, text):
            self.setFormat(match.start(), match.end() - match.start(), fmt)

    def _highlight_regex(self, text: str, pattern: str, fmt: QTextCharFormat, group: int = 0):
        for match in re.finditer(pattern, text):
            start, end = match.span(group)
            if start >= 0 and end > start:
                self.setFormat(start, end - start, fmt)

    def highlightBlock(self, text: str):
        if not text:
            return

        if self.lang_name == "Python (.py)":
            self._highlight_words(text, self.PYTHON_KEYWORDS, self.fmt_keyword)
            self._highlight_words(text, self.PYTHON_BUILTINS, self.fmt_builtin)
            self._highlight_regex(text, r"\b\d+(\.\d+)?\b", self.fmt_number)
            self._highlight_regex(text, r"(\".*?\"|'.*?')", self.fmt_string)
            self._highlight_regex(text, r"#.*$", self.fmt_comment)

        elif self.lang_name == "HTML (.html)":
            self._highlight_regex(text, r"</?\s*[\w-]+", self.fmt_tag)
            self._highlight_regex(text, r"/?>", self.fmt_tag)
            self._highlight_regex(text, r"\b([\w-]+)\s*=", self.fmt_attr, group=1)
            self._highlight_regex(text, r"(\".*?\"|'.*?')", self.fmt_string)
            self._highlight_regex(text, r"<!--.*?-->", self.fmt_comment)

        elif self.lang_name == "CSS (.css)":
            self._highlight_regex(text, r"^([^{}/]+)\{", self.fmt_selector, group=1)
            self._highlight_regex(text, r"([\w-]+)\s*:", self.fmt_css_prop, group=1)
            self._highlight_regex(text, r":\s*([^;{}]+)", self.fmt_css_val, group=1)
            self._highlight_regex(text, r"#(?:[0-9a-fA-F]{3,8})\b", self.fmt_number)
            self._highlight_regex(text, r"/\*.*?\*/", self.fmt_comment)

        elif self.lang_name == "JavaScript (.js)":
            self._highlight_words(text, self.JS_KEYWORDS, self.fmt_keyword)
            self._highlight_regex(text, r"\b\d+(\.\d+)?\b", self.fmt_number)
            self._highlight_regex(text, r"(`.*?`|\".*?\"|'.*?')", self.fmt_string)
            self._highlight_regex(text, r"//.*$", self.fmt_comment)

        elif self.lang_name == "C++ (.cpp)":
            self._highlight_words(text, self.CPP_KEYWORDS, self.fmt_keyword)
            self._highlight_regex(text, r"#\s*\w+", self.fmt_builtin)
            self._highlight_regex(text, r"\b\d+(\.\d+)?\b", self.fmt_number)
            self._highlight_regex(text, r"(\".*?\"|'.*?')", self.fmt_string)
            self._highlight_regex(text, r"//.*$", self.fmt_comment)

        else:
            self._highlight_regex(text, r"\b\d+(\.\d+)?\b", self.fmt_number)
            self._highlight_regex(text, r"(\".*?\"|'.*?')", self.fmt_string)
            self._highlight_regex(text, r"(#.*$|//.*$)", self.fmt_comment)


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
    """Окрема вкладка редактора з номерами рядків, підсвіткою, автодоповненням та мовою."""

    PAIRS = {
        "(": ")",
        "[": "]",
        "{": "}",
        '"': '"',
        "'": "'",
        "`": "`",
    }
    CLOSING_CHARS = set(PAIRS.values())
    SELF_CLOSING_HTML_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr", "!DOCTYPE"
    }

    def __init__(self, lang_name="Python (.py)", file_path=None, content="", font_size=13):
        super().__init__()
        self.lang_name = lang_name
        self.file_path = file_path
        self.is_modified = False

        self.setFont(QFont("Consolas", font_size))
        self.line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.highlighter = UniversalHighlighter(self.document(), self.lang_name)

        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)
        self._update_completer_model()

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

    def _update_completer_model(self):
        words = COMPLETION_WORDS.get(self.lang_name, [])
        self.completer.setModel(QStringListModel(words, self.completer))

    def word_under_cursor(self) -> str:
        cursor = self.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        return cursor.selectedText()

    def insert_completion(self, completion: str):
        cursor = self.textCursor()
        prefix = self.completer.completionPrefix()
        extra = len(completion) - len(prefix)
        if extra > 0:
            cursor.insertText(completion[-extra:])
        self.setTextCursor(cursor)

    def _auto_close_html_tag(self, cursor: QTextCursor):
        if self.lang_name != "HTML (.html)":
            return False

        line_before = cursor.block().text()[:cursor.positionInBlock()]
        if line_before.endswith("-->") or re.search(r"</[\w-]+\s*>$", line_before):
            return False

        match = re.search(r"<([\w!-]+)(?:\s[^<>]*)?>$", line_before)
        if not match:
            return False

        tag_name = match.group(1)
        if tag_name.lower() in self.SELF_CLOSING_HTML_TAGS or tag_name.startswith("!"):
            return False

        line_after = cursor.block().text()[cursor.positionInBlock():]
        closing = f"</{tag_name}>"
        if line_after.startswith(closing):
            return False

        cursor.insertText(">" + closing)
        cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(closing))
        self.setTextCursor(cursor)
        return True

    def keyPressEvent(self, event):
        """Ручне введення без автодоповнення та автоматичної вставки символів."""
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

        # Решта клавіш вводиться буквально: без шаблонів,
        # автозакриття тегів, дужок, лапок чи автоматичних відступів.
        if self.completer.popup().isVisible():
            self.completer.popup().hide()
        super().keyPressEvent(event)

    def _indent_selection(self, unindent: bool = False):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        start_block = self.document().findBlock(start)
        end_block = self.document().findBlock(end)

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

    def _trigger_word_completer(self):
        words = COMPLETION_WORDS.get(self.lang_name, [])
        if not words:
            self.completer.popup().hide()
            return

        prefix = self.word_under_cursor()
        if len(prefix) < 2:
            self.completer.popup().hide()
            return

        if prefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(prefix)
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))

        rect = self.cursorRect()
        rect.setWidth(
            self.completer.popup().sizeHintForColumn(0)
            + self.completer.popup().verticalScrollBar().sizeHint().width()
            + 20
        )
        self.completer.complete(rect)

    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        space = 14 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

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
                number_text = str(block_number + 1)
                if block_number == current_block_number:
                    painter.setPen(QColor("#ffffff"))
                else:
                    painter.setPen(QColor("#6e7681"))

                painter.drawText(
                    0, top,
                    self.line_number_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignRight | Qt.AlignVCenter,
                    number_text
                )

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#1e2330")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def set_language(self, lang_name: str):
        self.lang_name = lang_name
        self.highlighter.set_language(lang_name)
        self._update_completer_model()

    def _on_text_changed(self):
        self.is_modified = True


class TerminalInput(QLineEdit):
    """Поле вводу команд термінала з підтримкою історії (стрілки Вгору/Вниз)."""
    def __init__(self, on_submit_callback):
        super().__init__()
        self.on_submit_callback = on_submit_callback
        self.history = []
        self.history_index = -1

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cmd = self.text().strip()
            if cmd:
                if not self.history or self.history[-1] != cmd:
                    self.history.append(cmd)
                self.history_index = len(self.history)
                self.clear()
                self.on_submit_callback(cmd)
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

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 6)
        main_layout.setSpacing(8)

        # Легка верхня панель
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.btn_folder = QPushButton("📁 Папка")
        self.btn_folder.setToolTip("Відкрити робочу папку проєкту")

        self.btn_new = QPushButton("+ Вкладка")
        self.btn_new.setToolTip("Створити нову вкладку (Ctrl+N)")

        self.btn_open = QPushButton("📂 Відкрити")
        self.btn_open.setToolTip("Відкрити файл з комп'ютера")

        self.btn_save = QPushButton("💾 Зберегти")
        self.btn_save.setToolTip("Зберегти поточний файл (Ctrl+S)")

        self.lang_selector = QComboBox()
        self.lang_selector.addItems(list(LANG_EXTENSIONS.keys()))
        self.lang_selector.setMinimumWidth(155)
        self.lang_selector.setToolTip("Мова програмування або формат файлу")

        self.btn_run = QPushButton("▶ Запустити")
        self.btn_run.setObjectName("runBtn")
        self.btn_run.setToolTip("Запустити код або відкрити HTML у браузері (F5)")

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
        toolbar.addStretch()
        toolbar.addWidget(self.btn_font_down)
        toolbar.addWidget(self.btn_font_up)
        toolbar.addWidget(self.btn_toggle_term)
        main_layout.addLayout(toolbar)

        h_splitter = QSplitter(Qt.Horizontal)

        # Чиста бічна панель файлів
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

        # Центр: редактор + компактний термінал
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
        self.console_label = QLabel("Вивід і термінал")
        self.btn_clear = QPushButton("Очистити")
        self.btn_clear.setObjectName("ghostBtn")
        self.btn_clear.setToolTip("Очистити вивід термінала")
        console_top.addWidget(self.console_label)
        console_top.addStretch()
        console_top.addWidget(self.btn_clear)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 11))
        self.console.setObjectName("console")

        cmd_row = QHBoxLayout()
        self.prompt_badge = QLabel(">")
        self.prompt_badge.setObjectName("promptBadge")
        self.terminal_input = TerminalInput(self.run_terminal_command)
        self.terminal_input.setFont(QFont("Consolas", 11))
        self.terminal_input.setPlaceholderText("Введи команду та натисни Enter (наприклад: py --version або cls)...")
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

        # Рядок стану знизу з підказками та індикатором шрифту
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_hint_label = QLabel(
            f"Шрифт: {self.editor_font_size} pt   •   F5 — Запуск   •   Ctrl+S — Зберегти   •   Ctrl+N — Нова вкладка"
        )
        self.status_hint_label.setObjectName("statusHint")
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
        self.btn_font_down.clicked.connect(lambda: self.change_font_size(-1))
        self.btn_font_up.clicked.connect(lambda: self.change_font_size(1))
        self.btn_clear.clicked.connect(self.console.clear)
        self.btn_toggle_term.toggled.connect(self.toggle_terminal)
        self.btn_exec_cmd.clicked.connect(self._submit_input_button)
        self.lang_selector.currentTextChanged.connect(self.on_language_changed)

        self.file_tree.doubleClicked.connect(self.on_tree_double_clicked)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        QShortcut(QKeySequence("F5"), self).activated.connect(self.run_code)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_file)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.create_new_tab)
        QShortcut(QKeySequence("Ctrl+="), self).activated.connect(lambda: self.change_font_size(1))
        QShortcut(QKeySequence("Ctrl++"), self).activated.connect(lambda: self.change_font_size(1))
        QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(lambda: self.change_font_size(-1))
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(
            lambda: self.close_tab(self.tabs.currentIndex())
        )

        self.apply_styles()
        self.create_new_tab()
        # Після створення вкладок одразу показуємо текстові файли поточної робочої папки.
        self.open_workspace_files()

    def change_font_size(self, delta: int):
        new_size = max(9, min(32, self.editor_font_size + delta))
        if new_size == self.editor_font_size:
            return
        self.editor_font_size = new_size
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, EditorTab):
                tab.set_editor_font_size(self.editor_font_size)
        self.status_hint_label.setText(
            f"Шрифт: {self.editor_font_size} pt   •   F5 — Запуск   •   Ctrl+S — Зберегти   •   Ctrl+N — Нова вкладка"
        )

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
                font-family: 'Consolas', monospace;
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

    def _selected_item_path(self) -> str | None:
        index = self.file_tree.currentIndex()
        if not index.isValid():
            return None
        path = os.path.abspath(self.file_model.filePath(index))
        if os.path.exists(path):
            return path
        return None

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

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if not isinstance(tab, EditorTab) or not tab.file_path:
                continue
            tab_abs = os.path.abspath(tab.file_path)

            if tab_abs == old_abs:
                tab.file_path = new_abs
                ext = os.path.splitext(new_abs)[1].lower()
                for name, lang_ext in LANG_EXTENSIONS.items():
                    if lang_ext == ext:
                        tab.set_language(name)
                        if i == self.tabs.currentIndex():
                            self.lang_selector.blockSignals(True)
                            self.lang_selector.setCurrentText(name)
                            self.lang_selector.blockSignals(False)
                        break
                self.update_tab_title(i)

            elif os.path.isdir(new_abs):
                prefix = old_abs + os.sep
                if tab_abs.startswith(prefix):
                    rel = tab_abs[len(prefix):]
                    tab.file_path = os.path.join(new_abs, rel)
                    self.update_tab_title(i)

    def _close_open_tabs_for_deleted_path(self, deleted_path: str):
        del_abs = os.path.abspath(deleted_path)
        for i in range(self.tabs.count() - 1, -1, -1):
            tab = self.tabs.widget(i)
            if not isinstance(tab, EditorTab) or not tab.file_path:
                continue
            tab_abs = os.path.abspath(tab.file_path)
            if tab_abs == del_abs or tab_abs.startswith(del_abs + os.sep):
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
            self,
            "Перейменувати",
            f"Нова назва для «{old_name}»:",
            text=old_name
        )
        if not ok or not new_name.strip():
            return

        clean_new_name = new_name.strip()
        if clean_new_name == old_name:
            return

        new_path = os.path.abspath(os.path.join(parent_dir, clean_new_name))
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Назва зайнята", f"Об'єкт «{clean_new_name}» уже існує.")
            return

        try:
            os.rename(target_path, new_path)
            self._update_open_tabs_after_rename(target_path, new_path)
            self.status_bar.showMessage(f"Перейменовано в «{clean_new_name}»", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося перейменувати:\n{e}")

    def delete_selected_item(self):
        target_path = self._selected_item_path()
        if not target_path:
            QMessageBox.information(self, "Видалення", "Спочатку вибери файл або папку у списку зліва.")
            return

        item_name = os.path.basename(target_path)
        is_dir = os.path.isdir(target_path)
        kind_label = "папку з усім вмістом" if is_dir else "файл"

        reply = QMessageBox.question(
            self,
            "Видалити?",
            f"Видалити {kind_label} «{item_name}»?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            if is_dir:
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
            self,
            "Новий файл",
            "Ім'я файлу (наприклад: index.html, style.css, app.py):"
        )
        if not ok or not file_name.strip():
            return

        clean_name = file_name.strip()
        new_file_path = os.path.abspath(os.path.join(target_dir, clean_name))
        parent_dir = os.path.dirname(new_file_path)

        try:
            os.makedirs(parent_dir, exist_ok=True)
            if os.path.exists(new_file_path):
                self.open_paths_in_tabs([new_file_path])
                return

            with open(new_file_path, "w", encoding="utf-8") as f:
                f.write("")

            self.open_paths_in_tabs([new_file_path])
            self.status_bar.showMessage(f"Створено файл {clean_name}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити файл:\n{e}")

    def create_folder_in_sidebar(self):
        target_dir = self._target_directory_for_creation()
        folder_name, ok = QInputDialog.getText(
            self,
            "Нова папка",
            "Назва нової папки:"
        )
        if not ok or not folder_name.strip():
            return

        new_folder_path = os.path.abspath(os.path.join(target_dir, folder_name.strip()))
        try:
            os.makedirs(new_folder_path, exist_ok=True)
            self.status_bar.showMessage(f"Створено папку {folder_name.strip()}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити папку:\n{e}")

    def set_workspace_folder(self, folder_path: str):
        if folder_path and os.path.isdir(folder_path):
            abs_folder = os.path.abspath(folder_path)
            self.workspace_dir = abs_folder
            root_idx = self.file_model.setRootPath(abs_folder)
            self.file_tree.setRootIndex(root_idx)
            folder_name = os.path.basename(abs_folder) or abs_folder
            self.sidebar_label.setText(folder_name)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Обрати папку проєкту", self.workspace_dir)
        if folder:
            self.set_workspace_folder(folder)
            self.terminal_cwd = os.path.abspath(folder)
            self.console_label.setText(f"Термінал • {self.terminal_cwd}")
            self.open_workspace_files()

    def collect_workspace_text_files(self):
        """Знаходить текстові файли проєкту, пропускаючи службові та дуже великі файли."""
        root = os.path.abspath(self.workspace_dir)
        found = []

        for current_dir, dir_names, file_names in os.walk(root, followlinks=False):
            # Не заходимо в каталоги залежностей, кешів та зібраних результатів.
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
        """Відкриває всі знайдені текстові файли робочої папки в окремих вкладках."""
        paths = self.collect_workspace_text_files()
        if paths:
            self.open_paths_in_tabs(paths)
            self.status_bar.showMessage(
                f"Відкрито файлів проєкту: {len(paths)} (службові папки та файли понад 2 МБ пропущено)",
                6000
            )
        else:
            self.status_bar.showMessage("У папці проєкту не знайдено підтримуваних текстових файлів", 5000)

    def on_tree_double_clicked(self, index: QModelIndex):
        if not index.isValid():
            return
        file_path = self.file_model.filePath(index)
        if os.path.isfile(file_path):
            self.open_paths_in_tabs([file_path])

    def _submit_input_button(self):
        cmd = self.terminal_input.text().strip()
        if cmd:
            if not self.terminal_input.history or self.terminal_input.history[-1] != cmd:
                self.terminal_input.history.append(cmd)
            self.terminal_input.history_index = len(self.terminal_input.history)
            self.terminal_input.clear()
            self.run_terminal_command(cmd)

    def sync_terminal_cwd_with_editor(self):
        editor = self.current_editor()
        if editor and editor.file_path:
            folder = os.path.dirname(os.path.abspath(editor.file_path))
            if os.path.isdir(folder):
                self.terminal_cwd = folder
                self.console_label.setText(f"Термінал • {self.terminal_cwd}")
                self.set_workspace_folder(folder)

    def run_terminal_command(self, cmd: str):
        self.console.appendPlainText(f"> {cmd}")

        if cmd.lower() in ("cls", "clear"):
            self.console.clear()
            return

        if cmd.lower() == "cd" or cmd.lower().startswith("cd "):
            target = cmd[2:].strip().strip('"').strip("'")
            if not target:
                self.console.appendPlainText(self.terminal_cwd)
                return
            new_path = os.path.abspath(os.path.join(self.terminal_cwd, target))
            if os.path.isdir(new_path):
                self.terminal_cwd = new_path
                self.console_label.setText(f"Термінал • {self.terminal_cwd}")
                self.set_workspace_folder(new_path)
            else:
                self.console.appendPlainText(f"Шлях не знайдено: {new_path}")
            return

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.terminal_cwd,
                capture_output=True,
                text=True,
                timeout=20
            )
            if result.stdout:
                self.console.appendPlainText(result.stdout.rstrip())
            if result.stderr:
                self.console.appendPlainText(result.stderr.rstrip())
            if not result.stdout and not result.stderr:
                self.console.appendPlainText("[Готово]")
        except subprocess.TimeoutExpired:
            self.console.appendPlainText("[Помилка]: Час виконання команди вичерпано (20 сек).")
        except Exception as e:
            self.console.appendPlainText(f"[Помилка термінала]: {e}")

    def current_editor(self) -> EditorTab | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, EditorTab) else None

    def update_tab_title(self, index: int):
        editor = self.tabs.widget(index)
        if not isinstance(editor, EditorTab):
            return
        if editor.file_path:
            name = os.path.basename(editor.file_path)
        else:
            ext = LANG_EXTENSIONS.get(editor.lang_name, ".txt")
            name = f"новий{ext}"

        if editor.is_modified:
            name += " *"
        self.tabs.setTabText(index, name)

        if index == self.tabs.currentIndex():
            title_path = editor.file_path if editor.file_path else name
            self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — {title_path}")

    def create_new_tab(self, checked=False, lang_name=None, file_path=None, content=""):
        if lang_name is None:
            lang_name = self.lang_selector.currentText()
        if content is None:
            content = ""

        editor = EditorTab(
            lang_name=lang_name,
            file_path=file_path,
            content=content,
            font_size=self.editor_font_size
        )
        editor.is_modified = False

        index = self.tabs.addTab(editor, "")
        editor.textChanged.connect(lambda _=None, ed=editor: self.update_tab_title(self.tabs.indexOf(ed)))

        self.tabs.setCurrentIndex(index)
        self.update_tab_title(index)

    def close_tab(self, index: int):
        if index < 0:
            return
        editor = self.tabs.widget(index)
        if isinstance(editor, EditorTab) and editor.is_modified:
            reply = QMessageBox.question(
                self,
                "Незбережені зміни",
                "Закрити вкладку без збереження змін?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.create_new_tab()

    def on_tab_changed(self, index: int):
        editor = self.current_editor()
        if editor:
            self.lang_selector.blockSignals(True)
            self.lang_selector.setCurrentText(editor.lang_name)
            self.lang_selector.blockSignals(False)
            self.update_tab_title(index)

    def on_language_changed(self, lang_name: str):
        editor = self.current_editor()
        if not editor:
            return
        editor.set_language(lang_name)
        self.update_tab_title(self.tabs.currentIndex())

    def open_paths_in_tabs(self, paths):
        for path in paths:
            abs_path = os.path.abspath(path)
            already_open = False
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if isinstance(tab, EditorTab) and tab.file_path == abs_path:
                    self.tabs.setCurrentIndex(i)
                    already_open = True
                    break
            if already_open:
                continue

            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(abs_path, "r", encoding="cp1251", errors="replace") as f:
                    content = f.read()

            ext = os.path.splitext(abs_path)[1].lower()
            detected_lang = "Текст (.txt)"
            for name, lang_ext in LANG_EXTENSIONS.items():
                if lang_ext == ext:
                    detected_lang = name
                    break

            curr = self.current_editor()
            if (
                self.tabs.count() == 1
                and curr is not None
                and not curr.file_path
                and not curr.is_modified
            ):
                curr.file_path = abs_path
                curr.set_language(detected_lang)
                curr.blockSignals(True)
                curr.setPlainText(content)
                curr.blockSignals(False)
                curr.is_modified = False
                self.lang_selector.setCurrentText(detected_lang)
                self.update_tab_title(0)
            else:
                self.create_new_tab(lang_name=detected_lang, file_path=abs_path, content=content)

        self.sync_terminal_cwd_with_editor()

    def open_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Відкрити файли",
            self.terminal_cwd,
            "Усі підтримувані файли (*.py *.html *.css *.js *.cpp *.c *.json *.txt);;Усі файли (*)"
        )
        if paths:
            self.open_paths_in_tabs(paths)

    def save_file(self):
        editor = self.current_editor()
        if not editor:
            return

        default_ext = LANG_EXTENSIONS.get(editor.lang_name, ".txt")

        if not editor.file_path:
            default_name = "index.html" if default_ext == ".html" else (
                "style.css" if default_ext == ".css" else f"main{default_ext}"
            )
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Зберегти файл",
                os.path.join(self.terminal_cwd, default_name),
                "Усі файли (*)"
            )
            if not path:
                return
            editor.file_path = os.path.abspath(path)

        with open(editor.file_path, "w", encoding="utf-8") as f:
            f.write(editor.toPlainText())

        editor.is_modified = False
        self.update_tab_title(self.tabs.currentIndex())
        self.sync_terminal_cwd_with_editor()
        self.status_bar.showMessage(f"Збережено: {os.path.basename(editor.file_path)}", 3000)

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
        self.console.clear()

        if ext == ".py":
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
                tmp.write(code)
                tmp_path = tmp.name
            try:
                result = subprocess.run(
                    [sys.executable, tmp_path],
                    cwd=self.terminal_cwd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.stdout:
                    self.console.appendPlainText(result.stdout.strip())
                if result.stderr:
                    self.console.appendPlainText(f"[Помилка]:\n{result.stderr.strip()}")
                if not result.stdout and not result.stderr:
                    self.console.appendPlainText("[Виконано без виводу]")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        elif ext == ".html":
            if editor.file_path and os.path.exists(editor.file_path):
                if editor.is_modified:
                    self.save_file()
                webbrowser.open("file://" + os.path.abspath(editor.file_path))
                self.console.appendPlainText(f"[Відкрито у браузері]: {editor.file_path}")
            else:
                with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tmp:
                    tmp.write(code)
                    tmp_path = tmp.name
                webbrowser.open("file://" + os.path.abspath(tmp_path))
                self.console.appendPlainText(f"[Відкрито тимчасовий HTML у браузері]: {tmp_path}")

        elif ext == ".js":
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
                tmp.write(code)
                tmp_path = tmp.name
            try:
                result = subprocess.run(
                    ["node", tmp_path],
                    cwd=self.terminal_cwd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.stdout:
                    self.console.appendPlainText(result.stdout.strip())
                if result.stderr:
                    self.console.appendPlainText(f"[Помилка Node.js]:\n{result.stderr.strip()}")
            except FileNotFoundError:
                self.console.appendPlainText("[Інфо]: Для запуску .js потрібен встановлений Node.js.")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        else:
            self.console.appendPlainText(
                f"[Інфо]: Файл {ext} готовий. Відкрий вкладку HTML і натисни F5 для перегляду в браузері."
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CodeEditor()
    window.show()
    sys.exit(app.exec())
