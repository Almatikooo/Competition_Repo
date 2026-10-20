# Licensing of the Learn content

- **Readings (`excerpts.json`).** These are excerpts of the lead sections of English Wikipedia articles.
  - Wikipedia text is licensed under **[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)** by Wikipedia contributors.
  - Every excerpt stores the article title, a permanent link to the exact revision used (`permalink`, with `oldid`), and the date it was retrieved.
  - Some excerpts are shortened. These are marked `"trimmed": true` and show *shortened* in the app.
  - Formula markup and empty citation brackets are cleaned up. No other changes are made.
- **Lesson notes, activities and quizzes (`courses/*.json`).** These are written for Path.AI and released under **CC BY-SA 4.0**. They build on the excerpts above.
- **Code.** All code in this repository is under the repository's Apache-2.0 licence.

To refresh or rebuild the readings, run:

```bash
python scripts/build_learn_content.py            # fetch missing excerpts
python scripts/build_learn_content.py --refresh  # re-fetch every excerpt (new revisions)
```

After a refresh, re-check that every quiz question can still be answered from its lesson. Run `python -m pytest tests/test_learn.py`, then review the changed excerpts.
