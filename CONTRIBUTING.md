# Contributing to DroppedNeedle

Thanks for your interest. Bug reports, feature requests, and pull requests are all welcome.

## Reporting Bugs

Use the [bug report template](https://github.com/bross84/DroppedNeedle-Lite/issues/new?template=bug.yml). Include your DroppedNeedle version, steps to reproduce, and relevant logs from `docker compose logs droppedneedle`. The more detail you give, the faster things get fixed.

## Requesting Features

Use the [feature request template](https://github.com/bross84/DroppedNeedle-Lite/issues/new?template=feature.yml). Check existing issues first to avoid duplicates.

## Development Setup

The backend is Python 3.13 with FastAPI. The frontend is SvelteKit with Svelte 5, Tailwind CSS, and daisyUI.

### Prerequisites

- Python 3.13+
- Node.js 22+
- Docker (for building the full image)

### Running Locally

Backend:

```bash
cd backend
pip install -r requirements-dev.txt
cp env.dev.example .env
python -m maintenance.automatic_upgrade --start-target
```

That is what the container runs (see the `CMD` in the `Dockerfile`): it completes the
legacy-catalog migration, then serves `target_main:app`. Starting `uvicorn main:app`
directly runs the older application factory, which does not mount the target-only
routes the frontend expects — Settings > Library will report that it could not load.

Linux (or WSL) is the supported development environment. On native Windows the
backend will not start: `library_paths` defaults to `/music`, which is not an
absolute path there, and the startup upgrade cannot create its safety backup.

Frontend:

```bash
cd frontend
cp env.development.example .env.development
pnpm install
pnpm run dev
```

### Running Tests

```bash
make backend-test          # backend suite
make frontend-test         # frontend server and browser suites
make frontend-test-server  # frontend server suite only
make frontend-test-client  # frontend browser suite only
make test                  # backend and frontend server suites; excludes browser tests
```

Frontend browser tests use Playwright. Install the browser first:

```bash
make frontend-browser-install
```

## Pull Requests

1. Fork the repo and create a branch from `main`.
2. Give your branch a descriptive name: `fix-scrobble-timing`, `feature-playlist-export`, etc.
3. If you're fixing a bug, mention the issue number in the PR description.
4. Make sure tests pass before submitting.
5. Keep changes focused. One PR per fix or feature.

## Code Style

- Backend: strong typing, async/await, no blocking I/O in async contexts.
- Frontend: strict TypeScript, no `any`. Named exports. Async/await only.
- Use existing design tokens (`primary`, `secondary`, etc.) for colours, not hardcoded values.
- Run `pnpm run lint` and `pnpm run check` in the frontend before submitting.

## AI-Assisted Contributions

If you used AI tools (Copilot, ChatGPT, Claude, etc.) to write code in your PR, please mention it. This isn't a problem and won't get your PR rejected, but it helps reviewers calibrate how much scrutiny to apply. A quick note like "Claude helped with the caching logic" is enough.

You're still responsible for understanding and testing the code you submit.

## Questions?

For the application itself, upstream's [Discord](https://discord.gg/B5suDg7gu2) and [Discussions](https://github.com/DroppedNeedle/DroppedNeedle/discussions) are the right venues. For this fork, open an issue here.
