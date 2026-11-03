"""Narrow intent parser for actions the local Windows assistant can execute."""

import re


_TARGETS = {
    "youtube": "open youtube",
    "you tube": "open youtube",
    "google": "open google",
    "chrome": "open chrome",
    "google chrome": "open chrome",
    "notepad": "open notepad",
    "calculator": "open calculator",
    "paint": "open paint",
    "file explorer": "open file explorer",
    "command prompt": "open command prompt",
    "gmail": "open gmail",
    "github": "open github",
    "chatgpt": "open chatgpt",
    "wikipedia": "open wikipedia",
    "stack overflow": "open stack overflow",
    "geeksforgeeks": "open geeksforgeeks",
    "python documentation": "open python documentation",
}
_TARGET_PATTERN = "|".join(re.escape(name) for name in sorted(_TARGETS, key=len, reverse=True))
_URL_PATTERN = r"(?:https?://)?[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}(?:/[a-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?"


def classify_local_action(text):
    """Return a validated local action or None for ordinary questions.

    Only imperative open/launch/start/go-to requests and explicit web searches
    are accepted. Natural language questions such as "How do I open YouTube?"
    are deliberately left for the AI chat path.
    """
    if not isinstance(text, str):
        return None
    value = re.sub(r"\s+", " ", text.strip()).strip(" \t\r\n.!?")
    value = re.sub(r"^(?:hey\s+)?(?:jarvis|nexora)[, ]+", "", value, flags=re.I)

    compact = re.sub(r"\s+", " ", value.lower()).rstrip("?!.")
    if compact in {"time", "what time is it", "tell me the time"}:
        return {"command": "what time is it", "question": None}
    if compact in {"date", "what is the date", "tell me today's date"}:
        return {"command": "what is the date", "question": None}

    search = re.fullmatch(r"(?:please\s+)?search\s+(google|youtube)(?:\s+for)?\s+(.+)", value, re.I)
    if search:
        provider, query = search.groups()
        query = query.strip()
        if query:
            return {"command": f"search {provider.lower()} for {query}", "question": None}

    opening = re.fullmatch(
        rf"(?:please\s+)?(?:open|launch|start|go\s+to|navigate\s+to)\s+(?:the\s+)?(?P<target>{_TARGET_PATTERN}|{_URL_PATTERN})(?:\s+for\s+me)?(?:\s+and\s+(?:tell\s+me\s+)?(?P<question>.+))?",
        value,
        re.I,
    )
    if not opening:
        return None

    target = opening.group("target").lower()
    question = opening.group("question")
    if question:
        question = re.sub(r"^(?:tell\s+me|explain)\s+", "", question, flags=re.I).strip(" .?!")
        reversed_what = re.fullmatch(r"what\s+(.+?)\s+is", question, re.I)
        if reversed_what:
            question = f"What is {reversed_what.group(1)}?"
        elif re.match(r"^what\s+is\b|^what's\b", question, re.I):
            question = question[0].upper() + question[1:].rstrip("?!") + "?"
        elif question:
            question = f"What is {question}?"
        else:
            return None

    command = _TARGETS.get(target)
    if command is None:
        command = f"open {target if target.startswith(('http://', 'https://')) else 'https://' + target}"
    return {"command": command, "question": question}
