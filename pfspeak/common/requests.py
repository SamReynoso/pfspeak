import json
import time
import requests
from dataclasses import dataclass


@dataclass
class OllamaRequest:
    model: str
    port: int = 11434
    stream: bool = True
    protocol: str = "http"
    host: str = "127.0.0.1"
    tags: str = "/api/tags"
    pull_api: str = "/api/pull"
    generate: str = "/api/generate"

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    def request(self, prompt: str):
        url = self.url + self.generate
        json ={
                "model": self.model,
                "prompt": prompt,
                "stream": self.stream,
                "keep_alive": "30m",
                }
        r = requests.post(url, json=json, stream=self.stream)
        r.raise_for_status()
        return r

    def ping(self, timeout: float = 3.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                r = requests.get(self.url + self.tags, timeout=1)
                r.raise_for_status()
                return True
            except requests.RequestException:
                time.sleep(0.25)
        return False

    def has_model(self) -> bool:
        r = requests.get(self.url + self.tags)
        r.raise_for_status()
        models = r.json()["models"]
        return any(m["name"] == self.model for m in models)

    def pull(self) -> None:
        url = self.url + self.pull_api
        data = {"name": self.model, "stream": True}
        r = requests.post(url, json=data, stream=True)
        new_line = True
        for line in r.iter_lines():
            if not line:
                continue
            update = json.loads(line.decode())
            if "completed" in update and "total" in update:
                progress_bar(float(update["completed"]),
                             float(update["total"]),
                             20)
                new_line = False
            elif "status" in update:
                ch = "" if new_line else "\n"
                print(f"{ch}Ollama: {update['status']}")
                new_line = True
        r.raise_for_status()


def progress_bar(completed: float, total: float, width: int):
    kwargs = {"end":"", "flush":True}
    meg_total = f"{total / 1024**2:.1f}"
    filled = int(completed / total * width)
    percent= f"{completed / total * 100:5.1f}"
    bar = "#" * filled + "-" * (width - filled)
    meg_completed = f"{completed / 1024**2:.1f}"

    print(f"\r[{bar}] {percent}% ({meg_completed}/{meg_total} MiB)", **kwargs)
