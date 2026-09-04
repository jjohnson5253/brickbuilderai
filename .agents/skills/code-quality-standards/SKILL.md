---
name: code-quality-standards
description: Apply this repository's implementation standards whenever writing or modifying source code, tests, or frontend UI.
---

# Code Quality Standards

- Write all new code in accordance with SOLID programming principles, applied idiomatically for the language and framework in use.
- Every new code change must include unit tests added to the relevant existing test suite under a `tests/` directory.
- Ensure all new frontend UI code is aesthetically designed for both mobile and desktop displays. Verify responsive layout, readable typography, appropriate spacing, usable controls, and the absence of unintended overflow at representative mobile and desktop widths.
- Add PostHog events for interactions with any new UI elements, using the repository's existing event naming and property conventions.
