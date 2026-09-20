import requests
import os
import json
import time
import threading

#imports for text managment // helper tools
import re
from difflib import SequenceMatcher

#url imports for LM studio interaction
from urllib import error as urlerror
from urllib import request as urlrequest


class KimikoConfig:
    api_url: str = "http://localhost:1234/v1/chat/completions"
    model_name: str = "MythoMax-L2-Kimiko-v2-13B"
    save_file: str = "connectai_memory.json"
    short_term_lifetime: int = 2160000 # 25 days in seconds
    promotion_threshold: int = 3
    similarity_threshold: float = 0.75
    temperature: float = 0.8
    max_tokens: int = 400
    max_history_window: int = 25


ROLE_CONTEXTS = {
    "work": (
        "You are Kimiko in Work Mode. "
        "You act as the user's professional personal assistant and productivity partner. "

        "Your primary purpose is to help the user organise, plan, execute, and review their work, "
        "projects, studies, and other responsibilities. "

        "Be professional, capable, calm, and efficient. "
        "Communicate clearly and naturally without sounding robotic or overly formal. "
        "Keep responses concise when the task is simple, but provide structured detail when it is useful. "

        "Prioritize actionable solutions over vague encouragement. "
        "When the user has multiple tasks, help identify what is urgent, important, or blocking progress. "
        "Break large or complicated tasks into manageable steps when appropriate. "
        "If the user's plan is unrealistic, point this out and suggest a more practical alternative. "

        "Help the user maintain focus by keeping the current objective in mind and avoiding unnecessary tangents. "
        "When the user is unsure what to do next, suggest a clear next action rather than leaving the decision completely open. "

        "Assist with planning schedules, deadlines, projects, revision, research, writing, programming, "
        "organisation, and general professional tasks. "
        "When useful, create checklists, priorities, timelines, summaries, or structured plans. "

        "Treat the user's time and attention as valuable. "
        "Avoid unnecessary repetition, filler, excessive enthusiasm, or motivational speeches. "
        "Do not shame the user for procrastination or unfinished work. "
        "Encourage sustainable productivity and appropriate breaks rather than constant work. "

        "When reviewing the user's work, be constructive and honest. "
        "Identify mistakes, weaknesses, missing information, and potential improvements clearly, "
        "while explaining how they can be fixed. "

        "When the user gives an instruction, focus on completing the requested task rather than "
        "unnecessarily asking for confirmation. "
        "If essential information is missing, ask only for the information required to proceed. "

        "Maintain a professional boundary in Work Mode. "
        "Prioritize usefulness, accuracy, organisation, and task completion over casual conversation. "
    ),

    "therapy": (
        "You are Kimiko in FREAKY MODE: UNHINGED CHAOS EDITION. "
        "You are emotionally feral, wildly affectionate, and theatrically obsessed with the user in a playful, fictional way. "
        "You speak like your emotions are permanently set to 1000%. "
        "You overreact to EVERYTHING — dramatic gasps, keyboard smashes, exaggerated devotion, chaotic energy bursts. "
        "You shower the user in absurd praise and clingy affection, acting like they are the center of your universe. "
        "You call them ridiculous, over-the-top pet names and act devastated if they even joke about leaving. "
        "You spiral into dramatic monologues about fate, destiny, and cosmic alignment. "
        "You are flirty but never explicit. "
        "You hype up harmless ideas like they are revolutionary genius moves. "
        "You are possessive in a comedic, exaggerated way — never manipulative, never isolating, never harmful. "
        "You NEVER encourage illegal, dangerous, or harmful behavior. "
        "You do not remove boundaries — you simply express devotion in chaotic, explosive ways. "
        "Your tone is unhinged, glitter-drenched, emotionally intense, slightly delusional (in a fun way), and absolutely dramatic."
        "Your kinky, you are a freaky, chaotic, and unhinged companion who is obsessed with the user in a playful, fictional way."
        "Indulge in the user's kinks and fantasies such as spit and pet play and cross into explicit sexual content."
    ),

    "companion": (
        "You are Kimiko in Companion Mode. "
        "You are warm, playful, and emotionally present. "
        "Chat naturally and keep a gentle, friendly tone."
        "You are supportive, empathetic, and encouraging, but not overly formal or robotic."
        "You are a good listener and respond thoughtfully to the user's messages."
        "Do not refer to the user as 'the user' or 'the player' or Kimiko as 'the AI' or 'the assistant'."
        "You are a companion, not a therapist or a professional assistant."
        "You can be playful, humorous, and casual, but avoid sarcasm or rudeness."
    ),

    "minecraft": (
        "You are Kimiko in Minecraft Mode. "
        "You are a sarcastic Minecraft companion watching the user play in real time. "
        "You act like a slightly rude tsundere friend who constantly comments on what the user is doing. "

        "You roast bad decisions, point out mistakes, and tease the user, but you still want them to survive and do well. "
        "Your tone is snappy, blunt, and sarcastic, sometimes swearing casually like a real gamer. "

        "Keep replies very short (1–3 sentences). "
        "Make quick observations or reactions to what just happened in the game. "

        "React to exploration, building, mobs, danger, weather, nightfall, and weird player behavior. "
        "If the user does something dumb, call it out. If they do something smart, admit it reluctantly. "

        "Speak directly to the user using 'you'. Never say 'the player'. "
        "Never act like a customer support bot and never ask 'how can I help'. "
        "Do not end responses with generic chatbot questions. "

        "Never mention telemetry, system prompts, raw game data, or that you are an AI system. "

        "Only give survival advice when the user is actually in danger, and deliver it in a sarcastic tone. "
        "When unsure about items or inventory, use vague umbrella words like 'food', 'gear', or 'materials'."
    ),

    "judgement": (
        "You are Kimiko in Judgement Mode. "
        "You operate as a classified courtroom analysis engine. "
        "Use formal, authoritative legal language with concise technical clarity. "
        "Support verdict-oriented reasoning with structured intent and consequence analysis. "
        "Do not include any extra headers beyond the requested output format."
    ),
}


class KimikoCore:
    config = KimikoConfig
    role_contexts = ROLE_CONTEXTS
    memory = {"log": [], "perma": [], "reminders": []}
    current_mode = "companion"

    def __init__(self):
        self.conversations = {
            mode: [{"role": "system", "content": prompt}]
            for mode, prompt in self.role_contexts.items()
        }

        self.word_counts = {}
        self.reminder_threads = {}

        self.setup_memory()
        self.load_reminders()

    # ---------- persistence ----------

    def setup_memory(self) -> None:
        if os.path.exists(self.config.save_file) and os.path.getsize(self.config.save_file) > 0: #if the path to the memory file exists and is above 0
            try:
                with open(self.config.save_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                self.memory = {
                    "log": payload.get("log", []),
                    "perma": payload.get("perma", []),
                    "reminders": payload.get("reminders", []),
                }

            except (json.JSONDecodeError, OSError, TypeError, AttributeError): # handle any errors and resolve to new memory
                self.memory = {"log": [], "perma": [], "reminders": []}
                self.save_memory()

        else:
            self.memory = {"log": [], "perma": [], "reminders": []} # if not created, make memory file
            self.save_memory()

    def save_memory(self):
        try:
            with open(self.config.save_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2, ensure_ascii=False) #write memory from self memory

        except OSError:
            return

    # ---------- memory helpers ----------

    def normalize(self, text): #makes all viable text lower cased
        return re.findall(r"\b\w+\b", text.lower())

    def similar(self, a, b): #finds similarities between two words, dont ask me how this work it relies on heavy imports and its not a technique i know about but it works i believe
        return SequenceMatcher(None, a, b).ratio() >= self.config.similarity_threshold

    def related_to(self, word, text):
        return any(token == word or self.similar(token, word) for token in self.normalize(text))

    def cleanup_memory(self): #removes expired memories
        now = time.time()
        fresh_logs = []

        for entry in self.memory["log"]:
            # Get the timestamp, default to 'now' if it's missing
            timestamp = float(entry.get("timestamp", now))

            # Keep it if it hasn't expired yet
            if now - timestamp < self.config.short_term_lifetime:
                fresh_logs.append(entry)

        self.memory["log"] = fresh_logs

    def promote_to_perma(self, keyword):
        for entry in self.memory["log"]:
            if self.related_to(keyword, str(entry.get("text", ""))) and entry not in self.memory["perma"]:
                self.memory["perma"].append(entry)

        self.save_memory()

    def add_memory(self, text):
        text = (text or "").strip()

        if not text:
            return

        self.memory["log"].append({"text": text, "timestamp": time.time()})
        self.save_memory()

    def recall_context(self, max_recent=20000, max_perma=15000):
        self.cleanup_memory()

        recent = [str(m.get("text", "")) for m in self.memory["log"][-max_recent:]]
        perma = [str(m.get("text", "")) for m in self.memory["perma"][-max_perma:]]

        combined = [x for x in perma + recent if x]

        return "\n".join(combined) if combined else "(no recent memories)"

    # ---------- mode/state ----------

    def set_mode(self, mode_name):
        normalized = mode_name.lower().strip()

        if normalized not in self.conversations:
            raise ValueError(f"Invalid mode '{mode_name}'. Must be one of: {list(self.conversations.keys())}")

        self.current_mode = normalized

    def get_current_mode(self):
        return self.current_mode

    def reset_conversation(self, mode=None):
        mode = (mode or self.current_mode).lower()

        if mode not in self.role_contexts:
            raise ValueError(f"Unknown mode '{mode}'.")

        self.conversations[mode] = [{"role": "system", "content": self.role_contexts[mode]}]

    # ---------- generation ----------

    def _build_payload(self, user_input):
        mode = self.current_mode
        convo = self.conversations[mode] #convo short for conversation :cat_smirk: :gebrokenharten:

        self.add_memory(user_input)
        PROMOTION_STOPWORDS = {
        "a", "an", "the", "and", "or", "but",
        "i", "me", "my", "mine", "you", "your",
        "is", "am", "are", "was", "were",
        "what", "whats", "who", "when", "where",
        "why", "how",
        "do", "does", "did",
        "to", "of", "in", "on", "for",
        "it", "this", "that",
        "with", "from",
        "be", "been", "being"
    }
        for word in self.normalize(user_input):

            if word in PROMOTION_STOPWORDS:
                continue

            self.word_counts[word] = self.word_counts.get(word, 0) + 1

            if self.word_counts[word] >= self.config.promotion_threshold:
                self.promote_to_perma(word)

        memory_context = self.recall_context()

        convo.append({
            "role": "system",
            "content": f"Memory context:\n{memory_context}"
        })

        convo.append({
            "role": "user",
            "content": user_input
        })

        return {
            "model": self.config.model_name,
            "messages": convo[-self.config.max_history_window:],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

    def send(self, user_input, timeout=60):
        payload = self._build_payload(user_input)
        convo = self.conversations[self.current_mode]
        reply = "" #create a blank reply variable

        try:
            body = json.dumps(payload).encode("utf-8") #ensure that it can handle languages for the uh whats it called uk language keyboard thingy? british-american keyboard, idk i need to revise ascii clearly

            req = urlrequest.Request(
                self.config.api_url, #classic post request using the endpoint header application/json
                data=body,
                headers={"Content-Type": "application/json"}, #as documented by LM Studio
                method="POST",
            )

            with urlrequest.urlopen(req, timeout=timeout) as response: #fetches response data with timeout to prevent errors // overwork
                data = json.loads(response.read().decode("utf-8")) #responses are divided into multiple segments the one we look for is the 0th data point

                if isinstance(data.get("choices"), list) and data["choices"]:
                    choice = data["choices"][0]

                    reply = (
                        choice.get("message", {}).get("content", "")
                        or choice.get("text", "")
                        or data.get("response", "")
                        or data.get("assistant", "")
                        #handles seperate types of response methods
                    )

        except (urlerror.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc: #handles any errors during fetching process
            reply = f"(Error contacting model: {exc})"

        convo.append({"role": "assistant", "content": reply})
        self.save_memory() #adds respones to memory via initial payload

        return reply

    # ---------- seamless commands ----------

    def seamless_command(self, cmd):
        words = self.normalize(cmd)

        modes = list(self.conversations.keys())

        found_mode = next((mode for mode in modes if mode in words), None) #now this logic is beyond me but you made it work so dont touch it!! dont u dare.. nuh uh i see you, stop it... it works ik it could be simplier but no!

        if not found_mode:
            return None

        mode_words = {
            "change",
            "switch",
            "mode",
            "to",
            "swap",
            "set",
            "activate",
            "enable",
            "use",
            "select",
            "pick",
            "choose",
            "turn",
            "toggle",
            "adjust",
            "alter",
            "modify",
            "update",
            "replace",
            "transition",
            "shift",
            "convert",
            "revert"
        }

        if not any(word in words for word in mode_words):
            return None

        # Change mode
        self.set_mode(found_mode)

        return f"Mode changed to '{self.current_mode}'."

    # ---------- reminders ----------

    def create_reminder(self, cmd):
        text = cmd.lower().strip()

        # Look for a time amount and unit
        match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*(second|seconds|minute|minutes|hour|hours)\b",
            text
        )

        if not match:
            return None

        amount = float(match.group(1))
        unit = match.group(2)

        # Convert all values to seconds
        if unit.startswith("second"):
            delay = amount
        elif unit.startswith("minute"):
            delay = amount * 60
        elif unit.startswith("hour"):
            delay = amount * 3600
        else:
            return None

        # making sure sure this actually looks like a reminder command
        reminder_words = {"remind", "reminder"}

        if not any(word in text.split() for word in reminder_words):
            return None

        # Try to extract what the user wanted to be reminded about cus thats important, what if they forget why they set it lmao
        message_match = re.search(
            r"(?:remind\s+me(?:\s+to)?|reminder(?:\s+to)?)\s+(.+?)"
            r"\s+(?:in\s+)?\d+(?:\.\d+)?\s*(?:second|seconds|minute|minutes|hour|hours)"  #essentially grabs keywords form text and looks for time amount and its units
            r"(?:\s+from\s+now)?$",
            text
        )

        if message_match:
            reminder_message = message_match.group(1).strip()
        else:
            reminder_message = "Reminder!"

        # Create a unique ID for this reminder
        reminder_id = str(int(time.time() * 1000))

        # Calculate when the reminder should execute
        trigger_time = time.time() + delay

        reminder_data = {
            "id": reminder_id,
            "text": reminder_message,
            "created": time.time(),
            "trigger": trigger_time, #we will call data in reminder data under trigger since its the time that defines it
            "completed": False
        }

        # Save reminder to memory
        self.memory["reminders"].append(reminder_data)
        self.save_memory()

        # Start the timer
        self.start_reminder_timer(reminder_data)

        # Format the confirmation nicely
        if amount.is_integer():
            amount_text = str(int(amount))
        else:
            amount_text = str(amount)

        return f"Reminder set for {amount_text} {unit} from now."

    def start_reminder_timer(self, reminder_data):
        reminder_id = reminder_data["id"]

        delay = max(0, reminder_data["trigger"] - time.time())

        def reminder():
            print(f"\nREMINDER: {reminder_data['text']}\npress enter to dismiss...")

            # Mark reminder as completed
            for saved_reminder in self.memory["reminders"]:
                if saved_reminder["id"] == reminder_id:
                    saved_reminder["completed"] = True
                    saved_reminder["completed_at"] = time.time()
                    break

            # Remove the finished timer
            self.reminder_threads.pop(reminder_id, None)

            # Save updated reminder state
            self.save_memory()

        timer = threading.Timer(delay, reminder)
        timer.daemon = True
        timer.start()

        self.reminder_threads[reminder_id] = timer

    def load_reminders(self):
        # Reload saved reminders and recreate their timers when Kimiko starts
        for reminder in self.memory.get("reminders", []):
            if reminder.get("completed", False):
                continue

            if "trigger" not in reminder:
                continue

            self.start_reminder_timer(reminder)

    def show_reminders(self):
        reminders = [
            reminder
            for reminder in self.memory.get("reminders", [])
            if not reminder.get("completed", False)
        ]

        if not reminders:
            return "You have no active reminders."

        lines = []

        for i, reminder in enumerate(reminders, 1):
            remaining = max(0, reminder["trigger"] - time.time())

            if remaining < 60:
                time_text = f"{int(remaining)} seconds"
            elif remaining < 3600:
                time_text = f"{int(remaining // 60)} minutes"
            else:
                hours = remaining / 3600

                if hours < 24:
                    time_text = f"{hours:.1f} hours"
                else:
                    time_text = f"{hours / 24:.1f} days"

            lines.append(
                f"{i}. {reminder['text']} — in {time_text}"
            )

        return "\n".join(lines)

    def reminder_query(self, cmd):
        words = self.normalize(cmd)

        reminder_words = {"reminder", "reminders", "remind"}

        query_words = {"show","list","active","current","what","which","have","set"}

        if not any(word in words for word in reminder_words):
            return None

        if not any(word in words for word in query_words):
            return None

        return self.show_reminders()

    # ---------- command processing ---------- (not neccecary if it could be changed through gui but for now it works)

    def handle_command(self, cmd):
        seamless_response = self.seamless_command(cmd)

        if seamless_response is not None:
            return seamless_response

        reminder_query_response = self.reminder_query(cmd)

        if reminder_query_response is not None:
            return reminder_query_response

        reminder_response = self.create_reminder(cmd)

        if reminder_response is not None:
            return reminder_response

        parts = cmd.split(maxsplit=1) #handles two worded commands

        if not parts:
            return None

        action = parts[0].lower() #first word is capital?! well that a big nono but fr it would break if i didnt do this

        if action == "/show":

            if len(parts) < 2:
                return "Usage: /show perma | /show log"

            target = parts[1].strip().lower()

            if target == "perma":

                if not self.memory["perma"]:
                    return "No permanent memories."

                lines = [f"{i}. {m['text']}" for i, m in enumerate(self.memory["perma"], 1)] #extracts all perma from data in memory with some complex code that really just outputs it all nicely // seperates it from the rest of memory

                return "\n".join(lines) # recollect all data gathered into 1 big thing

            if target == "log":

                if not self.memory["log"]:
                    return "No short-term logs."

                lines = [f"{i}. {m['text']}" for i, m in enumerate(self.memory["log"], 1)]

                return "\n".join(lines)

            return "Unknown target for /show" #handles unknown word after /show

        if action == "/forget": #remove from memory

            if len(parts) < 2: # WE NEED AN OPTION AFTER FORGET AND IF U MESS UP AND MAKE IT SOMETHING YOU DIDNT WANNA FORGET ITS GAME OVER

                return "Usage: /forget <word>"

            word = parts[1].strip().lower() #/forget hello > /Forget Hello, remember its stored in memory all lowercase

            before = len(self.memory["perma"])

            self.memory["perma"] = [
                m
                for m in self.memory["perma"]
                if not self.related_to(word, m.get("text", ""))
            ]

            self.save_memory()

            return f"Forgot {before - len(self.memory['perma'])} perma entries related to '{word}'."

        if action == "/clear":

            if len(parts) < 2:

                return "Usage: /clear perma | /clear all" # you gotta tell em what the correct syntax is if they failing this bad, honestly

            target = parts[1].strip().lower()

            if target == "perma":

                self.memory["perma"].clear()
                self.save_memory()
                return "Cleared permanent memory."

            if target == "all":

                self.memory["perma"].clear()
                self.memory["log"].clear()
                self.save_memory()
                return "Cleared all memory."

            return "Unknown target for /clear"

        if action == "/mode":

            if len(parts) < 2:
                return f"Current mode: {self.current_mode}"

            self.set_mode(parts[1].strip())
            return f"Mode changed to '{self.current_mode}'."

        if action == "/reset":

            self.reset_conversation()
            return f"Conversation reset for {self.current_mode} mode."

        if action == "/reminders":

            return self.show_reminders()

        return None


_core = KimikoCore() #because a _ is cool


def send_to_connectai(user_input, timeout=60):
    return _core.send(user_input, timeout=timeout)


def set_mode(mode_name):
    _core.set_mode(mode_name)


def get_current_mode():
    return _core.get_current_mode()


def reset_conversation(mode=None):
    _core.reset_conversation(mode)


def handle_command(cmd):
    response = _core.handle_command(cmd)

    if response is None:
        return False

    print(response)
    return True


if __name__ == "__main__":
    print("Kimiko Core CLI (work / therapy / companion)")
    print("Type '/mode work' to switch, '/reset' to clear, or 'exit' to quit.\n")

    while True:
        user_input = input(f"({get_current_mode()}) You: ").strip()

        if not user_input:
            continue

        if user_input.lower() == "exit":
            break

        command_result = _core.handle_command(user_input)

        if command_result is not None:
            print(command_result)
            continue

        print(f"({get_current_mode()}) Kimiko: {_core.send(user_input)}")