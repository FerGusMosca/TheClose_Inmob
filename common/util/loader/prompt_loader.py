import os

class PromptLoader:
    def __init__(self, prompts_path: str,prompt_name:str):
        self.prompts_path = prompts_path
        self.prompt_name=prompt_name
        self.prompts = {}
        self._load_all_prompts()

    def _load_all_prompts(self):
        """Loads only the requested .txt prompt file from the given directory."""
        found = False
        for file in os.listdir(self.prompts_path):
            if file.endswith(".txt") and file.replace(".txt", "") == self.prompt_name:
                found = True
                prompt_name = file.replace(".txt", "")
                with open(os.path.join(self.prompts_path, file), "r", encoding="utf-8") as f:
                    self.prompts[prompt_name] = f.read()
                    print(f"[PROMPT LOADER] Loaded prompt: {prompt_name} ({file}) ✅")
                break  # Ya lo encontraste, no sigas iterando

        if not found:
            raise FileNotFoundError(f"Prompt file '{self.prompt_name}.txt' not found in path '{self.prompts_path}'")

    def get_prompt(self, prompt_name: str) -> str:
        """Returns the prompt string for a given name."""
        return self.prompts.get(prompt_name, "")
