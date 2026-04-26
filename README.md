# poli-page-fastapi

FastAPI integration for [Poli Page](https://poli.page) — generate PDFs from path operations and background tasks with idiomatic `Depends()` injection.

> **Status**: scaffold only. Implementation begins in P1.2 of the [SDK roadmap](https://github.com/poli-page/poli-page/blob/develop/docs/onboarding/micka/sdk-roadmap.md).

## Install

```bash
pip install poli-page-fastapi
```

## Quick start

To be filled in as the integration is built. The package will expose a configurable `Depends`-able client provider, plus helpers for streaming PDF responses with the right `Content-Type` headers.

## Dependencies

This package depends on [`poli-page`](https://github.com/poli-page/sdk-python) (the core Python SDK, async-capable). It is automatically installed by pip. All HTTP, retry, and error-handling logic lives in the core SDK — this repo only adds FastAPI glue.

## Publishing

Published to **PyPI** as [`poli-page-fastapi`](https://pypi.org/project/poli-page-fastapi/).

## Documentation

Full Poli Page documentation is at [docs.poli.page](https://docs.poli.page).

## License

MIT — see [LICENSE](./LICENSE).
