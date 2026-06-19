import os


class Persona:
    """Loads a persona definition from a persona.md file."""

    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

    @classmethod
    def load(cls, path: str = "persona.md") -> "Persona":
        resolved = os.path.abspath(path)
        with open(resolved, "r", encoding="utf-8") as f:
            return cls(system_prompt=f.read())
