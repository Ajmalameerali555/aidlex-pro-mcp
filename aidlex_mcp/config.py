"""Validated operator configuration. Secrets never enter tool responses."""
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='AIDLEX_', env_file='.env', extra='ignore', populate_by_name=True)
    environment: Literal['development', 'production'] = 'development'
    auth_mode: Literal['public', 'bearer', 'oauth'] = 'public'
    public_base_url: str = 'http://localhost:8000'
    database_url: SecretStr = SecretStr('sqlite:///./data/aidlex.db')
    database_schema: str = 'aidlex_mcp'
    auto_migrate: bool = True
    bearer_token: SecretStr = SecretStr('')
    oauth_issuer: str = ''
    oauth_jwks_url: str = ''
    oauth_audience: str = ''
    oauth_algorithms: list[str] = ['RS256', 'ES256']
    allowed_origins: list[str] = ['https://chatgpt.com', 'https://chat.openai.com']
    allowed_hosts: list[str] = []
    allowed_subjects: list[str] = []
    rate_limit_per_minute: int = Field(default=120, ge=1, le=10000)
    analysis_limit_per_minute: int = Field(default=3, ge=1, le=60)
    max_body_bytes: int = Field(default=1500000, ge=10000, le=5000000)
    max_context_chars: int = Field(default=50000, ge=5000, le=150000)
    max_source_bytes: int = Field(default=2000000, ge=10000, le=5000000)
    source_max_age_days: int = Field(default=30, ge=1, le=365)
    max_candidate_chunks: int = Field(default=10000, ge=100, le=100000)
    openai_api_key: SecretStr = Field(default=SecretStr(''), validation_alias='OPENAI_API_KEY')
    model: str = ''
    reasoning_effort: Literal['none','low','medium','high','xhigh'] = 'high'
    embeddings_enabled: bool = False
    embedding_model: str = 'text-embedding-3-small'
    model_timeout_seconds: float = Field(default=35, ge=5, le=90)
    model_max_output_tokens: int = Field(default=7000, ge=1000, le=20000)
    research_network_enabled: bool = True

    @model_validator(mode='after')
    def validate_runtime(self):
        self.public_base_url = self.public_base_url.rstrip('/')
        base = urlsplit(self.public_base_url)
        if base.scheme not in ('http', 'https') or not base.hostname or base.query or base.fragment or base.path:
            raise ValueError('AIDLEX_PUBLIC_BASE_URL must be an origin without a path/query/fragment.')
        if base.username or base.password:
            raise ValueError('Credentials must not be placed in URLs.')
        if self.environment == 'production' and base.scheme != 'https':
            raise ValueError('Production requires an HTTPS public base URL.')
        if self.auth_mode == 'bearer' and len(self.bearer_token.get_secret_value()) < 40:
            raise ValueError('Developer bearer mode requires a random token of at least 40 characters.')
        if self.auth_mode == 'oauth':
            for label, value in [('issuer',self.oauth_issuer), ('jwks_url',self.oauth_jwks_url)]:
                parsed=urlsplit(value)
                if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError(f'OAuth {label} must be configured as an HTTPS URL.')
            if not self.oauth_audience:
                self.oauth_audience = self.public_base_url + '/mcp'
            if self.oauth_audience != self.public_base_url + '/mcp':
                raise ValueError('OAuth audience must equal the canonical public /mcp resource URL.')
        if set(self.oauth_algorithms) - {'RS256','ES256'}:
            raise ValueError('Only RS256 and ES256 signed access tokens are accepted.')
        if not self.database_schema.isidentifier():
            raise ValueError('Database schema must be a simple identifier.')
        if self.embeddings_enabled and not self.openai_api_key.get_secret_value():
            raise ValueError('Embeddings require OPENAI_API_KEY.')
        return self
