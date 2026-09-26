# Authentication and permissions

## Supported profiles

`public`: four public tools; no private case access and no server-side model execution.

`bearer`: one fixed developer identity using a locally generated random credential. Useful for tests and custom development clients only. It is not a multi-user account system or a substitute for ChatGPT-compatible OAuth.

`oauth`: resource-server JWT verification against a real external authorization provider. The authorization-code flow, PKCE, user login, consent and token issuance occur at that provider, not inside this server.

## Configure an established provider

Use a provider that can support ChatGPT's currently documented OAuth registration flow: a pre-registered client, supported dynamic registration, or client ID metadata documents as appropriate. Do not substitute a machine-to-machine application or a raw API key for a user authorization flow.

Configure authorization code with PKCE S256. Register the exact callback URI shown in your ChatGPT MCP management screen; callback formats can differ by provider capabilities and configuration. Do not guess a callback ID or allow a wildcard redirect.

Register an API/resource whose identifier is **your canonical public HTTPS `/mcp` URL**. The provider must issue signed JWT **access tokens** whose `aud` includes that exact URL and whose `iss` matches its metadata. An ID token, opaque token or token for another API is rejected. Where the client sends the OAuth `resource` parameter, configure the provider to honor it and issue the matching audience.

Supported signatures: RS256 or ES256. The provider must publish HTTPS JWKS and discovery metadata. Required token claims are `iss`, `aud`, `exp`, `iat` and a nonblank `sub`; `nbf` is enforced when present. Scopes are read from the standard space-separated `scope` string and/or string-array `scp` claim.

## Scopes and least privilege

| Scope | Purpose |
|---|---|
| `aidlex:read` | Read own cases, search, host analysis, timeline and citation work. |
| `aidlex:write` | Ingest own case documents and replace confirmed memory. |
| `aidlex:analyze` | Additional permission for optional billable model execution. |
| `aidlex:curate` | Privileged writes to the SHARED source library. Do not grant this to ordinary users. |
| `aidlex:delete` | Explicit deletion of own case data. |

Do not make every requested scope self-grantable. Enforce curator authorization at the identity provider, and require suitable consent for write/delete permissions. Public tool discovery alone does not grant these scopes.

Set `AIDLEX_ALLOWED_SUBJECTS` to a JSON array of real provider subject IDs for a restricted pilot. Leave it empty only when all correctly authenticated users with the relevant scopes should be allowed. The database owner key is a hash of issuer plus subject; callers cannot supply or override it.

## Discovery endpoints

The server publishes protected-resource metadata at `/.well-known/oauth-protected-resource` and `/.well-known/oauth-protected-resource/mcp`. Private tool calls without sufficient authorization return an MCP authentication challenge; invalid credentials receive HTTP 401. Signing keys are cached with expiry and bounded refresh.

The server does **not** publish an authorization endpoint, token endpoint, user-password database or refresh-token issuer. Those belong to your selected authorization provider. No client secret or signing private key is required in this resource server.

## Verification sequence

Run `python scripts/doctor.py` in the configured environment. It checks configuration, database connectivity, provider discovery, HTTPS endpoints and advertised PKCE. It does not prove the provider actually issues the intended audience/scopes.

Then complete a real ChatGPT sign-in. Verify two distinct accounts cannot access one another's records. Check expiry, revoked access, required scopes, curator restrictions and erasure. Keep access-token lifetimes short according to your security policy. This server validates signed tokens locally and does not perform per-request token introspection; an already-issued token can remain valid until expiry.

Reference: https://developers.openai.com/plugins/build/auth
