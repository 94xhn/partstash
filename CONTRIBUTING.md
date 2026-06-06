# Contributing to PartStash

Thanks for taking the time to contribute! PartStash is a small project, so the
process is light.

## Development setup

```bash
git clone https://github.com/94xhn/partstash.git
cd partstash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Run the app:

```bash
streamlit run app.py
```

Run the checks before opening a PR:

```bash
ruff check .
pytest
```

## Architecture rule of thumb

Keep **data logic** in the `partstash/` package and **UI** in `app.py`.

- Anything that transforms data, classifies a part, or reads/writes the store goes
  in `core.py`, `classify.py`, or `store.py` and **must have a test**.
- `app.py` should only wire widgets to those functions. If you find yourself writing
  a non-trivial transform inside `app.py`, move it into the package first.

This separation is what lets the test suite run without launching Streamlit — please
preserve it.

## Pull requests

- One focused change per PR.
- Add or update tests for any behaviour change.
- Keep the existing code style; `ruff` enforces the basics.
- Update `CHANGELOG.md` under an `## [Unreleased]` heading.

## Reporting bugs

Open an issue with: what you did, what you expected, what happened, and — if it's an
import problem — a small **anonymised** sample of the spreadsheet that triggered it
(strip prices/vendors if you'd rather not share them).
