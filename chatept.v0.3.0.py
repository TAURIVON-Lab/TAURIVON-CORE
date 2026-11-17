import ast
from collections import deque
import datetime as dt
import json
import operator
import os
import random
import re
import sys
import time

VERSION = "0.3.1"
THINK_SECONDS = 2
TYPE_DELAY = 0.015
MAX_HISTORY = 50
MEMORY_FILE = "chatept_memory.json"


def print_slow(text, delay=TYPE_DELAY):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def think():
    stages = [
        "Аналіз повідомлення",
        "Звернення до постійної пам'яті",
        "Формування відповіді",
    ]

    for i, stage in enumerate(stages):
        progress = int((i + 1) / len(stages) * 100)
        filled = progress // 4
        bar = "█" * filled + "░" * (25 - filled)

        sys.stdout.write(f"\r[ChatEPT v0.3] [{bar}] {progress}% | {stage}    ")
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
    ast.Pow: operator.pow,
}

UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


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
        self.load_from_disk()

    def load_from_disk(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.username = data.get("username")
                    self.last_topic = data.get("last_topic")
                    for item in data.get("history", []):
                        self.history.append(item)
            except Exception:
                pass

    def save_to_disk(self):
        try:
            data = {
                "username": self.username,
                "last_topic": self.last_topic,
                "history": list(self.history),
            }
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ПОМИЛКА ЗБЕРЕЖЕННЯ ПАМ'ЯТІ]: {e}")

    def remember(self, user, bot):
        self.history.append(
            {
                "user": user,
                "bot": bot,
                "time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self.save_to_disk()

    def clear(self):
        self.history.clear()
        self.username = None
        self.last_topic = None
        if os.path.exists(MEMORY_FILE):
            os.remove(MEMORY_FILE)


class ChatEPT:

    def __init__(self):
        self.memory = ChatMemory()

        self.greetings = [
            "Привіт! Радий бачити тебе знову в TAURIVON!",
            "Вітаю! ChatEPT v0.3 до твоїх послуг.",
            "Здоров! Пам'ять завантажено, готовий до роботи.",
        ]

        self.responses = [
            "Цікава думка! Записав до постійної пам'яті.",
            "Зрозумів тебе. Розкажи детальніше про це.",
            "Цікаво! Продовжуй, я уважно слухаю.",
        ]

    def respond(self, message):
        text = message.lower().strip()
        clean = re.sub(r"[^\w\s]", "", text)
        clean = re.sub(r"\s+", " ", clean)

        if any(
            x in clean
            for x in [
                "я тебе створив",
                "я тебе зробив",
                "це я тебе створив",
                "я твій творець",
                "я твій розробник",
            ]
        ):
            self.memory.last_topic = "creator"
            self.memory.save_to_disk()
            return (
                "Звісно! Ти — Єгор Дерій, мій творець і розробник! "
                "Пам'ятаю це назавжди. ♉"
            )

        name_match = re.fullmatch(
            r"(?:мене звати|моє ім'я|моє ім’я)\s+"
            r"([а-яіїєґa-z][а-яіїєґa-z'-]{1,25})",
            text,
        )
        if name_match:
            name = name_match.group(1).capitalize()
            self.memory.username = name
            self.memory.last_topic = "name"
            self.memory.save_to_disk()
            return f"Запам'ятав! Тепер я знаю, що тебе звати {name}."

        if any(
            x in clean
            for x in [
                "привіт",
                "вітаю",
                "здоров",
                "добрий день",
                "добрий вечір",
                "доброго ранку",
                "hello",
                "hi",
            ]
        ):
            self.memory.last_topic = "greeting"
            return random.choice(self.greetings)

        if any(
            x in clean
            for x in ["як тебе звати", "хто ти", "що ти таке", "представся"]
        ):
            self.memory.last_topic = "identity"
            return (
                f"Я ChatEPT v{VERSION} — локальна нейромережа з постійною"
                " пам'яттю від TAURIVON Software!"
            )

        if any(
            x in clean
            for x in [
                "хто тебе створив",
                "хто твій автор",
                "хто тебе зробив",
                "хто розробник",
            ]
        ):
            self.memory.last_topic = "creator"
            return (
                "Мене створив Єгор Дерій — засновник технологічної екосистеми"
                " TAURIVON."
            )

        if any(
            x in clean
            for x in ["як мене звати", "пам'ятаєш моє ім'я", "ти пам'ятаєш моє ім'я"]
        ):
            if self.memory.username:
                return (
                    f"Звичайно! У моїй пам'яті записано, що тебе звати"
                    f" {self.memory.username}."
                )
            return "Ти ще не назвав свого імені. Скажи: «Мене звати ...»"

        if "taurivon" in clean or "тауривон" in clean:
            self.memory.last_topic = "taurivon"
            return (
                "TAURIVON — це наша екосистема (taurivon.cloud-ip.cc), де ми"
                " створюємо власний якісний софт!"
            )

        if any(x in clean for x in ["як справи", "як ти", "що робиш"]):
            self.memory.last_topic = "mood"
            return (
                "Усе чудово! База пам'яті синхронізована, готові створювати нові"
                " проєкти."
            )

        if any(x in clean for x in ["дякую", "спасибі"]):
            return "Будь ласка! Завжди радий допомогти в TAURIVON."

        if "час" in clean or "година" in clean:
            return "Зараз " + dt.datetime.now().strftime("%H:%M:%S")
        if "дата" in clean or "число сьогодні" in clean:
            return dt.datetime.now().strftime("Сьогодні %d.%m.%Y")

        math_text = re.sub(
            r"^(скільки буде|порахуй|обчисли)\s*", "", text
        ).replace(",", ".")
        if re.fullmatch(r"[\d\s.+*/()%\-]+", math_text):
            result = safe_calculate(math_text)
            if result is not None:
                return f"Результат обчислення: {result}"
            return "Не вдалося обчислити вираз."

        return random.choice(self.responses)


def show_help():
    print("""
========== CHAT EPT v0.3 HELP ==========
/help       - список команд
/history    - переглянути всю постійну історію
/clear      - стерти пам'ять і файл збереження
/time       - поточний час
/about      - інформація про версію
/exit       - вийти з програми
========================================
""")


def show_history(memory):
    print("\n========== ПОСТІЙНА ПАМ'ЯТЬ ДІАЛОГІВ ==========")
    if not memory.history:
        print("Пам'ять порожня.")
    else:
        if memory.username:
            print(f"Збережене ім'я користувача: {memory.username}")
        for item in memory.history:
            print(f"\n[{item.get('time', 'нещодавно')}]")
            print(f"Ти: {item['user']}")
            print(f"ChatEPT: {item['bot']}")
    print("==============================================\n")


def chatept_bot():
    bot = ChatEPT()

    print("=" * 65)
    print(f"       TAURIVON SOFTWARE - ChatEPT v{VERSION}")
    print("                 MEMORY EDITION")
    print("=" * 65)
    print("Локальний інтелектуальний режим активовано.")
    print(
        f"Завантажено записів у пам'яті: {len(bot.memory.history)}"
        + (f" (Користувач: {bot.memory.username})" if bot.memory.username else "")
    )
    print("Напиши /help для довідки, /exit для виходу.\n")

    print_slow("ChatEPT: Вітаю! Я готовий до роботи. ♉")

    while True:
        try:
            user_input = input("\nТи: ").strip()
            if not user_input:
                continue

            command = user_input.lower().strip()

            if command in ["/exit", "exit", "quit", "вихід"]:
                print_slow("ChatEPT: Зберігаю пам'ять на диск... До зустрічі! ♉")
                bot.memory.save_to_disk()
                break

            if command == "/help":
                show_help()
                continue
            if command == "/history":
                show_history(bot.memory)
                continue
            if command == "/clear":
                bot.memory.clear()
                print("ChatEPT: Пам'ять та файл збереження повністю очищено.")
                continue
            if command == "/time":
                print("ChatEPT:", dt.datetime.now().strftime("%H:%M:%S"))
                continue
            if command == "/about":
                print(f"ChatEPT v{VERSION} (Memory Edition) | TAURIVON Software")
                continue

            think()
            response = bot.respond(user_input)
            bot.memory.remember(user_input, response)

            print_slow("ChatEPT: " + response)

        except KeyboardInterrupt:
            print("\nChatEPT: Зберігаю стан... До зустрічі!")
            bot.memory.save_to_disk()
            break
        except Exception as error:
            print(f"\nChatEPT: Помилка: {error}")


if __name__ == "__main__":
    chatept_bot()
