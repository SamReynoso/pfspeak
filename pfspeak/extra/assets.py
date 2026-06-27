

from pfspeak.common import models
from pfspeak.common.defaults import DEFAULT_APP_SPEC, AppSpec, Voices
from pfspeak.core.repos import RecognizerRepo, SpeechRepo


class AssetManager:

    def __init__(self,
                app: AppSpec | None = None,
                speech_repo: SpeechRepo | None = None,
                recognizer_repo: RecognizerRepo | None = None
                ) -> None:
        self.app = app or DEFAULT_APP_SPEC
        self.speech_repo = speech_repo or SpeechRepo()
        self.recognizer_repo = recognizer_repo or RecognizerRepo()

    def parent_directories(self):
        for directory in (self.app.data_dir,
                          self.app.cache_dir,
                          self.app.config_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def create_config_file(self, template: str):
        self.app.config_file.write_text(template)

    def download_missing(self):
        for repo in (self.speech_repo, self.recognizer_repo):
            local_dir = self.app.models_dir / repo.model_dir_name
            downloader = models.install_model(self.app, repo)
            for source_file in repo.MANIFEST:
                local_path = local_dir / source_file
                if not local_path.exists():
                    download_path = downloader(source_file)
                    try:
                        assert local_path == download_path
                    except AssertionError:
                        raise RuntimeError(
                                "unable to download reqiered model data"
                                )

    def download_voice(self, voice_lebal: str | Voices):
        downloader = models.install_model(self.app, self.speech_repo)
        path = downloader(self.speech_repo.voice_filename(voice_lebal))
        return path

    def info(self):

        for repo in (self.speech_repo, self.recognizer_repo):
            print("repo:", repo.model_label)
            print("repo:", repo.model_id)
            for source_file in repo.MANIFEST:
                print("source:", repo.model_id + "/" + source_file)
                print(
                        "path:",
                        self.app.models_dir / repo.model_dir_name / source_file
                        )

        for voice in Voices:
            print(
                    self.app.models_dir /
                    self.speech_repo.model_dir_name /
                    self.speech_repo.voice_filename(voice)
                  )
