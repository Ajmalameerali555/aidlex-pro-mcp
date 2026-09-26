"""Deployment specs must not use legacy routes or leak developer credentials."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('build_do_spec', Path(__file__).parents[1] / 'scripts/build_do_spec.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_public_spec_uses_current_size_and_ingress():
    result = module.make_spec('test-owner/test-repo', 'fra')
    service = result['services'][0]
    assert service['instance_size_slug'] == 'apps-s-1vcpu-1gb-fixed'
    assert 'routes' not in service
    assert result['ingress']['rules'][0]['component'] == {'name': 'mcp', 'preserve_path_prefix': True}
    assert result['ingress']['rules'][0]['match'] == {'path': {'prefix': '/'}}
    assert service.get('source_dir', '.') == '.'
    env = {item['key']: item for item in service['envs']}
    assert env['AIDLEX_PUBLIC_BASE_URL']['value'] == '${APP_URL}'
    assert env['AIDLEX_ENVIRONMENT']['value'] == 'production'


def test_private_spec_requires_persistent_postgres():
    with pytest.raises(ValueError, match='PostgreSQL'):
        module.make_spec('test-owner/test-repo', 'fra', values={
            'AIDLEX_AUTH_MODE': 'oauth', 'AIDLEX_OAUTH_ISSUER': 'https://id.example.test/',
            'AIDLEX_OAUTH_JWKS_URL': 'https://id.example.test/keys',
            'AIDLEX_DATABASE_URL': 'sqlite:///data/test.db'})


def test_bearer_profile_cannot_be_published():
    with pytest.raises(ValueError, match='not static bearer'):
        module.make_spec('test-owner/test-repo', 'fra', values={'AIDLEX_AUTH_MODE': 'bearer'})


def test_private_spec_marks_secrets_and_discards_developer_token():
    result = module.make_spec('test-owner/test-repo', 'fra', values={
        'AIDLEX_AUTH_MODE': 'oauth', 'AIDLEX_OAUTH_ISSUER': 'https://id.example.test/',
        'AIDLEX_OAUTH_JWKS_URL': 'https://id.example.test/keys',
        'AIDLEX_DATABASE_URL': 'postgresql://user:synthetic@db.example.test/aidlex',
        'AIDLEX_PUBLIC_BASE_URL': 'https://mcp.example.test',
        'AIDLEX_BEARER_TOKEN': 'synthetic-token', 'OPENAI_API_KEY': 'synthetic-key'})
    env = {item['key']: item for item in result['services'][0]['envs']}
    assert 'AIDLEX_BEARER_TOKEN' not in env
    assert env['AIDLEX_DATABASE_URL']['type'] == 'SECRET'
    assert env['OPENAI_API_KEY']['type'] == 'SECRET'
    assert env['AIDLEX_OAUTH_AUDIENCE']['value'] == 'https://mcp.example.test/mcp'
