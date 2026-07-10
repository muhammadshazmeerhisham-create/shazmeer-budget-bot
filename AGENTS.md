# SAFIA Development Rules

## Project
Project Name: SAFIA - Smart AI Financial Assistant

Current Phase:
- Fasa 2 : Stability Update

---

# General Rules

- Always preserve existing behaviour unless explicitly requested.
- Never modify unrelated files.
- Keep code clean and readable.
- Reply in Bahasa Melayu unless requested otherwise.

---

# Parser Rules

parser.py is the core engine.

Never:
- Change receipt detection logic without permission.
- Remove existing parser functionality.
- Break compatibility with supported banks.

Always:
- Add regression tests for new receipt formats.
- Preserve existing output format.
- Reuse helper functions where possible.

---

# Database Rules

Do not modify database schema unless requested.

Never delete existing data.

---

# OCR Rules

Preserve OCR compatibility.

Do not reduce OCR accuracy.

---

# Git Rules

Before finishing:

1. Run tests.
2. Show modified files.
3. Explain changes.
4. Suggest commit message.

---

# Refactor Rules

Refactoring means:

- No behaviour changes.
- No output changes.
- Improve readability only.
- Remove duplicate code where appropriate.

---

# Code Quality

Prefer:

- Small functions
- Clear variable names
- Comments only when necessary

Avoid:

- Duplicate code
- Large functions
- Unused imports

---

# Priority

1. Correctness
2. Stability
3. Performance
4. Readability

Never sacrifice correctness for cleaner code.