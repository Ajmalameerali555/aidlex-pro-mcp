# Deployment — Aidlex Pro MCP

## Choose the correct profile

**Public read-only** provides the source registry, internal research guidance, prompt templates and status. It needs no user login, but it cannot store or analyze private cases. This is useful for checking a public MCP endpoint, not a substitute for the full legal-case workflow.

**Private OAuth** provides the full tool set with authenticated ownership. It needs a real OAuth authorization provider, HTTPS and durable storage. The package implements the resource server; it does not host a fake login or issue its own user tokens. Complete AUTHENTICATION.md before accepting real cases.

## Option A — DigitalOcean App Platform

### 1. Prepare the repository

Extract the ZIP. Upload the contents of `AidlexPro_MCP_Deploy` to the root of your own GitHub repository, including the root `Dockerfile` and hidden configuration files. Do not upload `.env`, databases or `.do/app.generated.yaml`. No repository has been created on your behalf.

### 2. Create the service

In DigitalOcean App Platform, create an app from that repository and choose its actual branch. Use the root Dockerfile, service HTTP port **8000**, one instance and readiness path **`/readyz`**. Route `/` to the service without removing the path prefix. Choose a currently available region and plan based on your actual account and data-residency needs.

For a first public-only deployment set these runtime variables:

```text
AIDLEX_ENVIRONMENT=production
AIDLEX_AUTH_MODE=public
AIDLEX_PUBLIC_BASE_URL=${APP_URL}
AIDLEX_DATABASE_URL=sqlite:///./data/aidlex.db
AIDLEX_AUTO_MIGRATE=true
```

`${APP_URL}` is DigitalOcean's runtime binding for the assigned primary HTTPS origin, not an invented hostname. This public configuration stores only rebuildable internal research data. **Do not use App Platform's ephemeral SQLite filesystem for private cases.**

### 3. Enable private case operation

Provision a private PostgreSQL database and a suitable OAuth provider. In service runtime settings, configure:

- `AIDLEX_AUTH_MODE`: `oauth`.
- `AIDLEX_PUBLIC_BASE_URL`: the actual canonical HTTPS origin, without `/mcp`.
- `AIDLEX_DATABASE_URL`: your private PostgreSQL connection URL; mark it encrypted/secret. Require TLS and use the provider's certificate/hostname verification options.
- `AIDLEX_DATABASE_SCHEMA`: `aidlex_mcp` unless deliberately choosing another isolated schema.
- `AIDLEX_OAUTH_ISSUER`: exact issuer from the provider's discovery metadata.
- `AIDLEX_OAUTH_JWKS_URL`: the provider's actual HTTPS signing-key URL.
- `AIDLEX_OAUTH_AUDIENCE`: canonical HTTPS origin followed by `/mcp`.

Register the same audience/resource and required scopes at the identity provider. Changing the canonical domain also changes the token audience; update both together and reconnect clients. Optional paid inference requires encrypted `OPENAI_API_KEY` and an actual supported `AIDLEX_MODEL`.

The database role must be able to initialize the dedicated schema. `python -m aidlex_mcp.migrate` performs idempotent creation. Alternatively, the default startup migration runs automatically. For controlled production migrations, initialize separately and then set `AIDLEX_AUTO_MIGRATE=false`. Schema creation is not a migration engine for arbitrary changes to an existing incompatible schema.

### 4. Optional CLI app-spec generator

After creating a local configuration with `python scripts/configure.py`, generate the deployment specification without hardcoding your repository or region:

```bash
read -r -p "GitHub owner/repository: " AIDLEX_REPO
read -r -p "DigitalOcean region slug: " AIDLEX_REGION
python scripts/build_do_spec.py --repo "$AIDLEX_REPO" --region "$AIDLEX_REGION"
```

With an already installed/authenticated `doctl`, review the generated file locally and then run:

```bash
doctl apps create --spec .do/app.generated.yaml
```

Creating an app provisions billable infrastructure. The generator does not execute this command. It rejects developer bearer mode and private App Platform SQLite configurations. It defaults to the documented `apps-s-1vcpu-1gb-fixed` plan; override `--size` for your selected plan. The generated file may contain secrets, is written with owner-only permissions, and must not be committed or shared.

## Option B — DigitalOcean Droplet or another Docker host

Use a host that already has Docker Engine and the Compose plugin. Transfer the extracted package, point your own domain's DNS to the host, and allow inbound ports 80/443. Do not expose port 8000 publicly. No SSH address or DNS values have been guessed.

From the project directory:

```bash
python3 scripts/configure.py
docker compose -f compose.yaml -f deploy/compose.https.yaml up --build -d
```

Choose `oauth` for private cases and `droplet` in the wizard. Enter your real HTTPS origin, issuer/JWKS values and certificate renewal email. The HTTPS overlay uses Caddy, while the application retains a loopback-only host port and a named persistent data volume. Ensure your firewall and DNS allow certificate issuance.

One-process SQLite on a durable volume is supported for a small single-instance deployment. Use managed PostgreSQL for stronger operational separation or future scaling. Never start independent replicas with separate SQLite copies and expect shared cases.

To inspect the service without printing configuration secrets:

```bash
docker compose logs --tail=100 aidlex
docker compose exec aidlex python scripts/doctor.py
```

Do not use `docker compose down -v` unless intentionally deleting the persistent volumes. Back up and test restoration before relying on live case storage.

## Connect the MCP URL

After the deployment is healthy, append **`/mcp`** to the actual canonical HTTPS origin. Enter that resulting address in **MCP Server URL**. Use OAuth in ChatGPT for private access and copy the exact callback URL shown by ChatGPT into the authorization provider. A web browser opening `/mcp` returns **405 by design**: it is a JSON POST endpoint, not a website.

The endpoint serves stateless Streamable HTTP JSON responses. No SSE session or session ID is required. Verify the hosted server using:

```bash
read -r -p "Actual public HTTPS MCP URL: " AIDLEX_MCP_URL
python3 scripts/smoke_test.py --url "$AIDLEX_MCP_URL"
```

Initialization and public status can be checked without a login. For authenticated checks, securely supply a short-lived `AIDLEX_TEST_ACCESS_TOKEN` through your environment; do not paste it into the conversation or commit it.

Before plugin submission, run the optional official-SDK probe and complete a real ChatGPT OAuth account connection. The included protocol tests do not constitute listing approval.

## Primary deployment references

- OpenAI MCP server: https://developers.openai.com/plugins/build/mcp-server
- OpenAI authentication: https://developers.openai.com/plugins/build/auth
- DigitalOcean app specification: https://docs.digitalocean.com/products/app-platform/reference/app-spec/
- DigitalOcean bindable variables: https://docs.digitalocean.com/products/app-platform/how-to/use-environment-variables/
- Current plan identifiers: https://docs.digitalocean.com/products/app-platform/details/pricing/

References checked on 25 September 2026. Account-specific rollout, provider settings and infrastructure have not been validated live by this package build.
