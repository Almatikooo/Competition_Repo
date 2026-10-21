# Sources and terms of the Opportunities data

- **Job postings (`jobs.json`).** A dated snapshot built by `scripts/opportunities/jobs.py` from public, documented endpoints only:
  - company job boards through the public posting APIs of Greenhouse, Lever and Ashby (the employers are listed in `sources.json`);
  - Hacker News *Ask HN: Who is hiring?*, the latest monthly thread, through the Algolia HN Search API;
  - [Himalayas](https://himalayas.app/), [Jobicy](https://jobicy.com/), [Remotive](https://remotive.com/) and [Arbeitnow](https://www.arbeitnow.com/) through their public job APIs.

  For each posting only facts are kept: title, company, link, place, date, a level read from the title, and the skill and role ids our catalogue detects. Descriptions are read once to detect skills and are not stored or shown. Every job card names its source and links to the original posting, and applications always happen on the original page. We follow each feed's terms:
  - Remotive and Jobicy are credited with a link.
  - Remotive is queried only a few times a day.
  - Postings are never re-submitted to other job sites or used to collect sign-ups.
  - Raw responses are cached for 20 hours in `data/cache/` (not in git).
- **Places.** Location strings are mapped to countries with the [GeoNames](https://www.geonames.org/) gazetteer (CC BY 4.0), downloaded at build time into `data/cache/`.
- **Universities (`universities.json`).**
  - Sources: [Wikidata](https://www.wikidata.org/) (CC0 1.0), queried through the public QLever SPARQL endpoint, and the [Hipo university-domains-list](https://github.com/Hipo/university-domains-list) (MIT).
  - Order: each country's list is ordered by the number of Wikipedia language editions with an article about the institution. This is an open, rough sign of how widely an institution is known, not a ranking.
  - Rankings (QS, THE and others) are linked, not reproduced.
- **Links (`portals.json`, `fields.json`).** Curated by the Path.AI team; every URL was checked when added (see `checked`).
  - Job sites without a public API (JobStreet, SEEK, Indeed, LinkedIn, Naukri) are only linked with a search pre-filled. They are never fetched or scraped.

To refresh:

```bash
python -m scripts.opportunities.jobs           # about 8 minutes; polite, cached requests
python -m scripts.opportunities.universities
python -m pytest tests/test_opportunities.py
```
