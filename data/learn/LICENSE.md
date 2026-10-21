# Licensing of the Learn content

- **Lesson texts (`lessons/<skill>/*.html`).** Every lesson reproduces openly licensed material: MIT, CC0, CC BY 4.0, CC BY-SA 4.0,
  the UK Open Government Licence v3.0, the Design Science License, or U.S. Government works in the public domain. Each course file
  (`courses/<skill>.json`) lists its sources with name, URL, licence and the attribution to display, and every lesson links to its original.
  The app shows the source and licence on every lesson page. Text is re-typeset only: site navigation, newsletter boxes and similar
  chrome are removed, headings are re-levelled and long chapters are split at their own headings. Material under a ShareAlike licence
  (CC BY-SA) remains under that licence. No non-commercial (NC) sources are used.
- **Pinned versions.** GitHub sources are imported at the commit recorded in `pins.json`.
- **Chapter and final tests.** Questions marked `bank:` come from the open quiz banks of Microsoft's *for Beginners* curricula (MIT). Path.AI's own
  questions (`quizzes/<skill>.json`) are released under **CC BY-SA 4.0**; each one quotes the lesson sentence that answers it.
- **Code.** All code in this repository is under the repository's Apache-2.0 licence.

To rebuild the courses (sources are cached in `data/cache/learn/`):

```bash
uv run --with markdown-it-py --with mdit-py-plugins --with nh3 --with beautifulsoup4 --with lxml --with pyyaml \
  python -m scripts.learnkit.build            # all courses, or name skills: ... build sql excel
python -m pytest tests/test_learn.py          # licences, sanitising, grounded questions, API
```
