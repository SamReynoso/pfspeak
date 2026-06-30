import requests
from dataclasses import dataclass


@dataclass
class OllamaRequest:

    model: str

    protocal: str = "http"
    host: str = "127.0.0.1"
    port: int = 11434
    endpoint: str = "/api/generate"
    stream: bool = True

    @property
    def url(self) -> str:
        return f"{self.protocal}://{self.host}:{self.port}{self.endpoint}"

    
    def request(self, prompt: str):
        return requests.post(
                self.url,
                json={
                    "model":self.model,
                    "prompt":prompt,
                    "stream":self.stream,
                    },
                stream=self.stream,
                )
