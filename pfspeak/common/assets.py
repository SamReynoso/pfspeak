

from pfspeak.common import models
from pfspeak.common.defaults import AppSpec, Voices
from pfspeak.core.repos import RecognizerRepo, SpeechRepo


class AssetManager:

    def __init__(self, app: AppSpec) -> None:
        self.app = app

    def create_app_dirs(self):
        for directory in (self.app.data_dir,
                          self.app.cache_dir,
                          self.app.config_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def create_config_file(self, app, template: str):
        app.config_file.write_text(template)

    def download_missing(self, repo):
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
                            "Unable to download reqiered model data"
                            )

    def download_voice(self, repo, voice_lebal: str | Voices):
        downloader = models.install_model(self.app, repo)
        path = downloader(repo.voice_filename(voice_lebal))
        return path

    def info(self, repo):
        print("repo:", repo.model_label)
        print("repo:", repo.model_id)
        for source_file in repo.MANIFEST:
            print("source:", repo.model_id + "/" + source_file)
            print(
                    "path:",
                    self.app.models_dir / repo.model_dir_name / source_file
                    )

    def voice_info(self, repo):
        for voice in Voices:
            print("voice:", voice)
            print("path:",
                  self.app.models_dir /
                  repo.model_dir_name /
                  repo.voice_filename(voice)
                  )
