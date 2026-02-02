import os
import yaml
from pathlib import Path

class Config:
    def __init__(self):
        self._config = {}
        self.root_dir = Path(__file__).parent.parent
        self.config_path = self.root_dir / "config.yaml"
        self._load_config()

    def _load_config(self):
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        
    def get(self, key_path: str, default=None):
        """Get a configuration value using a dot-separated path."""
        keys = key_path.split(".")
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    @property
    def langfuse_enabled(self) -> bool:
        return str(self.get("langfuse.enabled", "false")).lower() == "true"

    @property
    def langfuse_public_key(self) -> str:
        return self.get("langfuse.public_key", "")

    @property
    def langfuse_secret_key(self) -> str:
        return self.get("langfuse.secret_key", "")

    @property
    def langfuse_host(self) -> str:
        return self.get("langfuse.host", "https://cloud.langfuse.com")

    @property
    def azure_openai_model_fast(self) -> str:
        return self.get("azure_openai.model_fast", "")

    @property
    def azure_openai_model_smart(self) -> str:
        return self.get("azure_openai.model_smart", "")

    @property
    def azure_openai_endpoint(self) -> str:
        return self.get("azure_openai.endpoint", "")

    @property
    def azure_openai_api_key(self) -> str:
        return self.get("azure_openai.api_key", "")

    @property
    def azure_openai_api_version(self) -> str:
        return self.get("azure_openai.api_version", "")

    @property
    def applicant_name(self) -> str:
        return self.get("applicant.name", "")

    @property
    def applicant_email(self) -> str:
        return self.get("applicant.email", "")

    @property
    def applicant_subject(self) -> str:
        return self.get("applicant.subject", "")

    @property
    def applicant_pdf(self) -> str:
        return self.get("applicant.pdf", "")

    @property
    def applicant_message(self) -> str:
        return self.get("applicant.message", "")

settings = Config()
