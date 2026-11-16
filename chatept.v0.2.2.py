import ast
import operator
import random
import re
import sys
import time
from datetime import datetime
from collections import deque

VERSION = "0.2.2"
THINK_SECONDS = 3
TYPE_DELAY = 0.015
MAX_HISTORY = 30


def print_slow(text, delay=TYPE_DELAY):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def think():
    stages = [
        "Аналіз повідомлення",
        "Обробка контексту діалогу",
        "Формування відповіді"
    ]

    for i, stage in enumerate(stages):
        progress = int((i + 1) / len(stages) * 100)
        filled = progress // 4
        bar = "█" * filled + "░" * (25 - filled)

        sys.stdout.write(
            f"\r[ChatEPT] [{bar}] {progress}% | {stage}    "
        )
        sys.stdout.flush()
        time.sleep(THINK_SECONDS / len(stages))

    print("\n")


OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow
}

UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg
}


def safe_calculate(expression):
    try:
        tree = ast.parse(expression, mode="eval")

        def calculate(node, depth=0):
            if depth > 20:
                raise ValueError()

            if isinstance(node, ast.Expression):
                return calculate(node.body, depth + 1)

            if isinstance(node, ast.Constant):
                if type(node.value) in (int, float):
                    if abs(node.value) > 10**12:
                        raise ValueError()
                    return node.value

            if isinstance(node, ast.BinOp):
                left = calculate(node.left, depth + 1)
                right = calculate(node.right, depth + 1)

                operation = OPERATORS.get(type(node.op))
                if operation is None:
                    raise ValueError()

                if isinstance(node.op, ast.Pow):
                    if abs(right) > 10 or abs(left) > 10**6:
                        raise ValueError()

                result = operation(left, right)

                if isinstance(result, (int, float)):
                    if abs(result) > 10**100:
                        raise ValueError()

                return result

            if isinstance(node, ast.UnaryOp):
                operation = UNARY_OPERATORS.get(type(node.op))
                if operation is None:
                    raise ValueError()
                return operation(calculate(node.operand, depth + 1))

            raise ValueError()

        result = calculate(tree)

        if isinstance(result, float) and result.is_integer():
            result = int(result)

        return result

    except ZeroDivisionError:
        return "Помилка: ділення на нуль!"
    except Exception:
        return None


class ChatMemory:
    def __init__(self):
        self.history = deque(maxlen=MAX_HISTORY)
        self.username = None
        self.last_topic = None

    def remember(self, user, bot):
        self.history.append({"user": user, "bot": bot})

    def clear(self):
        self.history.clear()
        self.username = None
        self.last_topic = None


class ChatEPT:
    def __init__(self):
        self.memory = ChatMemory()

        self.greetings = [
            "Привіт! Радий тебе бачити!",
            "Вітаю! ChatEPT готовий до розмови!",
            "Здоров! Як твої справи?",
            "Привіт! Що сьогодні обговоримо?"
        ]

        self.responses = [
            "Цікава думка! Розкажи про це детальніше.",
            "Зрозумів тебе. А що думаєш про це сам?",
            "Можеш пояснити трохи більше?",
            "Цікаво! Продовжуй, я слухаю."
        ]

    def respond(self, message):
        text = message.lower().strip()
        clean = re.sub(r"[^\w\s]", "", text)
        clean = re.sub(r"\s+", " ", clean)

        # Розробник
        if any(x in clean for x in [
            "я тебе створив",
            "я тебе зробив",
            "це я тебе створив",
            "я твій творець",
            "я твій розробник"
        ]):
            self.memory.last_topic = "creator"
            return (
                "Точно! Ти — Єгор Дерій, мій розробник "
                "і творець! Дякую, що нагадав! ♉"
            )

        # Ім'я користувача
        name_match = re.fullmatch(
            r"(?:мене звати|моє ім'я|моє ім’я)\s+"
            r"([а-яіїєґa-z][а-яіїєґa-z'-]{1,25})",
            text
        )

        if name_match:
            name = name_match.group(1).capitalize()
            self.memory.username = name
            self.memory.last_topic = "name"
            return f"Приємно познайомитися, {name}!"

        # Привітання
        if any(x in clean for x in [
            "привіт", "вітаю", "здоров",
            "добрий день", "добрий вечір",
            "доброго ранку", "hello", "hi"
        ]):
            self.memory.last_topic = "greeting"
            return random.choice(self.greetings)

        # Особистість
        if any(x in clean for x in [
            "як тебе звати", "хто ти",
            "що ти таке", "представся"
        ]):
            self.memory.last_topic = "identity"
            return (
                f"Я ChatEPT v{VERSION} — локальний діалоговий "
                "бот від TAURIVON Software!"
            )

        # Автор
        if any(x in clean for x in [
            "хто тебе створив", "хто твій автор",
            "хто тебе зробив", "хто розробник"
        ]):
            self.memory.last_topic = "creator"
            return "Мене створив Єгор Дерій — засновник TAURIVON!"

        # Ім'я
        if any(x in clean for x in [
            "як мене звати", "пам'ятаєш моє ім'я",
            "ти пам'ятаєш моє ім'я"
        ]):
            if self.memory.username:
                return f"Звичайно! Тебе звати {self.memory.username}."
            return "Ти ще не назвав свого імені."

        # TAURIVON
        if "taurivon" in clean or "тауривон" in clean:
            self.memory.last_topic = "taurivon"
            return (
                "TAURIVON — технологічний бренд Єгора Дерія, "
                "який розвиває програмне забезпечення та власні проєкти."
            )

        # Як справи
        if any(x in clean for x in [
            "як справи", "як ти",
            "що робиш", "як поживаєш"
        ]):
            self.memory.last_topic = "mood"
            return "Усе добре! Готовий продовжувати нашу розмову."

        # Подяка
        if any(x in clean for x in ["дякую", "спасибі"]):
            return "Будь ласка! Завжди радий допомогти."

        # Час
        if "час" in clean or "година" in clean:
            return "Зараз " + datetime.now().strftime("%H:%M:%S")

        # Дата
        if "дата" in clean or "число сьогодні" in clean:
            return datetime.now().strftime("Сьогодні %d.%m.%Y")

        # Погода
        if "погода" in clean:
            return "Я поки не підключений до сервісу прогнозу погоди."

        # Математика
        math_text = re.sub(
            r"^(скільки буде|порахуй|обчисли)\s*",
            "",
            text
        ).replace(",", ".")

        if re.fullmatch(r"[\d\s.+*/()%\-]+", math_text):
            result = safe_calculate(math_text)

            if result is not None:
                return f"Результат обчислення: {result}"

            return "Не вдалося обчислити вираз."

        # Контекст
        if clean in ["а чому", "чому", "чому саме", "навіщо"]:
            if self.memory.last_topic == "creator":
                return "Єгор створив мене як експериментальний проєкт TAURIVON."
            return "Можеш уточнити, про що саме запитуєш?"

        if clean in ["розкажи більше", "детальніше", "продовжуй"]:
            if self.memory.last_topic == "creator":
                return "Єгор розвиває TAURIVON як власну технологічну екосистему."
            return "Звичайно! Про яку саме тему хочеш дізнатися більше?"

        if clean in ["так", "ага", "зрозуміло", "добре"]:
            return "Чудово! Продовжимо. Що ще тебе цікавить?"

        if clean in ["ні", "не знаю"]:
            return "Нічого страшного. Можемо розібратися разом."

        return random.choice(self.responses)


def show_help():
    print("""
========== CHAT EPT HELP ==========

/help       - список команд
/history    - історія розмови
/clear      - очистити пам'ять
/time       - поточний час
/about      - інформація про програму
/exit       - завершити роботу

===================================
""")


def show_history(memory):
    print("\n========== ІСТОРІЯ ==========")

    if not memory.history:
        print("Історія порожня.")
    else:
        for item in memory.history:
            print(f"\nТи: {item['user']}")
            print(f"ChatEPT: {item['bot']}")

    print("=============================\n")


def chatept_bot():
    bot = ChatEPT()

    print("=" * 65)
    print(f"       TAURIVON SOFTWARE - ChatEPT v{VERSION}")
    print("                 DIALOGUE FIX UPDATE")
    print("=" * 65)
    print("Локальний діалоговий режим активовано.")
    print("Пам'ять діалогу: активна.")
    print("Напиши /help для перегляду команд.")
    print("Напиши /exit для завершення.\n")

    print_slow("ChatEPT: Вітаю! Я готовий до спілкування. ♉")

    while True:
        try:
            user_input = input("\nТи: ").strip()

            if not user_input:
                continue

            command = user_input.lower().strip()

            if command in ["/exit", "exit", "quit", "вихід"]:
                print_slow("ChatEPT: Завершую роботу. До зустрічі! ♉")
                break

            if command in [
                "бувай", "пака", "прощавай",
                "до побачення", "до зустрічі",
                "на все добре"
            ]:
                print_slow("ChatEPT: Бувай! Дякую за розмову! ♉")
                break

            if command == "/help":
                show_help()
                continue

            if command == "/history":
                show_history(bot.memory)
                continue

            if command == "/clear":
                bot.memory.clear()
                print("ChatEPT: Пам'ять діалогу очищено.")
                continue

            if command == "/time":
                print("ChatEPT:", datetime.now().strftime("%H:%M:%S"))
                continue

            if command == "/about":
                print(f"ChatEPT v{VERSION} | TAURIVON Software")
                continue

            think()
            response = bot.respond(user_input)
            bot.memory.remember(user_input, response)

            print_slow("ChatEPT: " + response)

        except KeyboardInterrupt:
            print("\nChatEPT: Сеанс перервано. До зустрічі!")
            break

        except EOFError:
            print("\nChatEPT: Завершення сеансу.")
            break

        except Exception as error:
            print(f"\nChatEPT: Внутрішня помилка: {error}")


if __name__ == "__main__":
    chatept_bot()
