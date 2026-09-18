# New User Setup Guide

This project is a local-first Context Companion app. Some files are generated at runtime and should not be committed to Git.

## 1) Clone the repository

```bash
git clone <your-repo-url>
cd context-companion-v1
```

## 2) Open the backend project in VS Code

The app logic lives under:

```text
context-companion/
  backend/
```

Open the backend folder in the VS Code terminal or use the project root as your workspace.

## 3) Create and activate a virtual environment

From the backend folder:

```bash
cd context-companion/backend
python -m venv .venv
```

On Windows:

```bash
.venv\Scripts\activate
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

## 4) Install dependencies

```bash
pip install -r requirements.txt
```

If you are doing development work:

```bash
pip install -r requirements-dev.txt
```

## 5) Configure environment variables

Copy the example file if needed:

```bash
copy .env.example .env
```

Or on Linux/macOS:

```bash
cp .env.example .env
```

The app uses values such as:

```env
LEARNED_CACHE_PATH=data/learned_concepts.db
LEXICAL_DICTIONARY_PATH=data/wordnet_dictionary.db
```

## 6) Start the backend

From the backend folder:

```bash
uvicorn app.main:app --reload
```

or:

```bash
python -m uvicorn app.main:app --reload
```

The app will start and create local SQLite databases automatically when needed.

## 7) Important: runtime DB files are local-only

The following files are generated when the app runs:

- `data/learned_concepts.db`
- `data/wordnet_dictionary.db`

These files are intentionally ignored by Git because they are runtime artifacts, not source files.

This is expected behavior. They will appear locally after the app initializes and will not normally appear in GitHub or git status unless you force-add them.

## 8) Why they are not in Git

The project includes a `.gitignore` rule for `.db` files, which prevents local SQLite databases from being committed.

This is normal for:

- generated cache files
- local runtime storage
- machine-specific data

## 9) Troubleshooting

### App does not start

Check the following:

- virtual environment is active
- dependencies are installed
- `.env` file exists
- Python version is compatible

### DB files do not appear

Run the backend once and let startup initialize the app. The database files are created on first use.

### Git status shows nothing for DB files

This is expected. The repo is configured to ignore them.

## 10) Good practice

Do not commit generated SQLite files unless you specifically need them for a local testing workflow. In most cases, keep them local and let the application recreate them.

## 11) Typical project folders

```text
context-companion/
  backend/
    app/
    data/
    tests/
    requirements.txt
    .env.example
    .env
```

## 12) Summary

For a new user, the project should work normally after setup:

1. create venv
2. install requirements
3. configure `.env`
4. run the backend
5. let the app generate the DB files locally

If the app starts successfully, your local environment is working as intended.
