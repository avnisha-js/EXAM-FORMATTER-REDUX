# Exam Formatter

One browser application routes each exam to an isolated Grade + Subject compartment.

English 10 is the only compartment in this build. Its formatting rules live in `subjects/english_10/` and are not shared with any other subject.

## Run

```bat
run_local.bat
```

Open `http://127.0.0.1:5000`.

Set `OPENAI_API_KEY` before adding the English 10 reference or formatting a conforming exam. Hierarchy discovery uses that key. `EXAM_REDO_MODEL` defaults to `gpt-4.1`.

## Tests

```bat
.venv\Scripts\python.exe -m pytest -m "not live"
.venv\Scripts\python.exe -m pytest -m live
```

The live tests certify the English reference and format the English fixtures. They call the model.
