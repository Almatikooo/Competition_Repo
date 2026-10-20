"""Which open course material each Path.AI course is built from — the editorial layer of the Learn tab.

Every lesson is a real chapter, episode or guide from an openly licensed curriculum (see SOURCES), kept whole or split at
its own section boundaries. Nothing here is paraphrased; the importer only cleans and re-typesets the original text.
"""

MIT = "https://opensource.org/license/mit"
CC_BY = "https://creativecommons.org/licenses/by/4.0/"
CC_BY_SA = "https://creativecommons.org/licenses/by-sa/4.0/"
CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"
OGL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
PD_US = "https://www.usa.gov/government-copyright"
DSL = "https://www.ibiblio.org/kuphaldt/electricCircuits/DC/DC_A3.html"
OGL_NOTE = "Contains public sector information licensed under the Open Government Licence v3.0"


def src(name, url, license, license_url, attribution, noncommercial=False):
    return {"name": name, "url": url, "license": license, "license_url": license_url, "attribution": attribution,
            "noncommercial": noncommercial}


def pd(name, url, who):
    return src(name, url, "Public domain (U.S. Government work)", PD_US, f"{who} — a U.S. Government work, not subject to copyright")


SOURCES = {
    # Microsoft open curricula
    "ms-ml": src("Microsoft · ML for Beginners", "https://github.com/microsoft/ML-For-Beginners", "MIT", MIT, "© Microsoft Corporation, MIT License"),
    "ms-ds": src("Microsoft · Data Science for Beginners", "https://github.com/microsoft/Data-Science-For-Beginners", "MIT", MIT, "© Microsoft Corporation, MIT License"),
    "ms-ai": src("Microsoft · AI for Beginners", "https://github.com/microsoft/AI-For-Beginners", "MIT", MIT, "© Microsoft Corporation, MIT License"),
    "ms-genai": src("Microsoft · Generative AI for Beginners", "https://github.com/microsoft/generative-ai-for-beginners", "MIT", MIT, "© Microsoft Corporation, MIT License"),
    "ms-agents": src("Microsoft · AI Agents for Beginners", "https://github.com/microsoft/ai-agents-for-beginners", "MIT", MIT, "© Microsoft Corporation, MIT License"),
    "ms-web": src("Microsoft · Web Dev for Beginners", "https://github.com/microsoft/Web-Dev-For-Beginners", "MIT", MIT, "© Microsoft Corporation, MIT License"),
    "ms-iot": src("Microsoft · IoT for Beginners", "https://github.com/microsoft/IoT-For-Beginners", "MIT", MIT, "© Microsoft Corporation, MIT License"),
    "ms-sec": src("Microsoft · Security 101", "https://github.com/microsoft/Security-101", "CC0 1.0", CC0, "Microsoft Security-101, dedicated to the public domain (CC0)"),
    "ms-pa": src("Microsoft Learn · Power Automate documentation", "https://github.com/MicrosoftDocs/power-automate-docs", "CC BY 4.0", CC_BY, "© Microsoft, CC BY 4.0"),
    "azure-arch": src("Microsoft · Azure Architecture Center (data guide)", "https://github.com/MicrosoftDocs/architecture-center", "CC BY 4.0", CC_BY, "© Microsoft, CC BY 4.0"),
    # The Carpentries
    "swc-python": src("Software Carpentry · Plotting and Programming in Python", "https://swcarpentry.github.io/python-novice-gapminder/", "CC BY 4.0", CC_BY, "© The Carpentries, CC BY 4.0"),
    "swc-sql": src("Software Carpentry · Databases and SQL", "https://swcarpentry.github.io/sql-novice-survey/", "CC BY 4.0", CC_BY, "© The Carpentries, CC BY 4.0"),
    "swc-shell": src("Software Carpentry · The Unix Shell", "https://swcarpentry.github.io/shell-novice/", "CC BY 4.0", CC_BY, "© The Carpentries, CC BY 4.0"),
    "swc-git": src("Software Carpentry · Version Control with Git", "https://swcarpentry.github.io/git-novice/", "CC BY 4.0", CC_BY, "© The Carpentries, CC BY 4.0"),
    "dc-sheets": src("Data Carpentry · Data Organization in Spreadsheets", "https://datacarpentry.github.io/spreadsheets-socialsci/", "CC BY 4.0", CC_BY, "© The Carpentries, CC BY 4.0"),
    "dc-openrefine": src("Data Carpentry · Data Cleaning with OpenRefine", "https://datacarpentry.github.io/openrefine-socialsci/", "CC BY 4.0", CC_BY, "© The Carpentries, CC BY 4.0"),
    "dc-geo": src("Data Carpentry · Introduction to Geospatial Concepts", "https://datacarpentry.github.io/organization-geospatial/", "CC BY 4.0", CC_BY, "© The Carpentries, CC BY 4.0"),
    "ci-docker": src("Carpentries Incubator · Introduction to Docker", "https://carpentries-incubator.github.io/docker-introduction/", "CC BY 4.0", CC_BY, "© The Carpentries, CC BY 4.0"),
    "ci-instructor": src("The Carpentries · Instructor Training", "https://carpentries.github.io/instructor-training/", "CC BY 4.0", CC_BY, "© The Carpentries, CC BY 4.0"),
    # Other open curricula & references
    "dair": src("DAIR.AI · Prompt Engineering Guide", "https://www.promptingguide.ai/", "MIT", MIT, "© DAIR.AI, MIT License"),
    "18f": src("18F Methods (U.S. GSA)", "https://methods.18f.gov/", "Public domain (CC0)", CC0, "18F, U.S. General Services Administration — public domain"),
    "ph": src("The Programming Historian", "https://programminghistorian.org/", "CC BY 4.0", CC_BY, "© The Programming Historian, CC BY 4.0"),
    "google-ml": src("Google for Developers · Machine Learning", "https://developers.google.com/machine-learning", "CC BY 4.0", CC_BY, "© Google, CC BY 4.0"),
    "google-cloud": src("Google Cloud · Architecture Center", "https://cloud.google.com/architecture", "CC BY 4.0", CC_BY, "© Google, CC BY 4.0"),
    "google-search": src("Google Search Central documentation", "https://developers.google.com/search/docs", "CC BY 4.0", CC_BY, "© Google, CC BY 4.0"),
    "scrum": src("The Scrum Guide (2020)", "https://scrumguides.org/scrum-guide.html", "CC BY-SA 4.0", CC_BY_SA, "© 2020 Ken Schwaber and Jeff Sutherland, CC BY-SA 4.0"),
    "lec": src("Lessons In Electric Circuits, Vol. I (DC)", "https://www.ibiblio.org/kuphaldt/electricCircuits/DC/", "Design Science License", DSL, "© Tony R. Kuphaldt, Design Science License"),
    # Open textbooks (Pressbooks / OpenStax)
    "bc-pm": src("Project Management, 2nd ed. (BCcampus)", "https://opentextbc.ca/projectmanagement/", "CC BY 4.0", CC_BY, "Adrienne Watt, BCcampus, CC BY 4.0"),
    "bc-gd": src("Graphic Design and Print Production Fundamentals (BCcampus)", "https://opentextbc.ca/graphicdesign/", "CC BY 4.0", CC_BY, "Ken Jeffery (ed.), BCcampus, CC BY 4.0"),
    "tour": src("Introduction to Tourism and Hospitality in BC, 2nd ed.", "https://opentextbc.ca/introtourism2e/", "CC BY 4.0", CC_BY, "Morgan Westcott and Wendy Anderson (eds.), BCcampus, CC BY 4.0"),
    "excel": src("Beginning Excel 2019 (Open Oregon)", "https://openoregon.pressbooks.pub/beginningexcel19/", "CC BY 4.0", CC_BY, "Noreen Brown, Barbara Lave, Hallie Puncochar, Julie Romey, Mary Schatz, Art Schneider and Diane Shingledecker, CC BY 4.0"),
    "finstrat": src("Financial Strategy for Public Managers", "https://ecampusontario.pressbooks.pub/financialstrategy/", "CC BY 4.0", CC_BY, "Sharon Kioko and Justin Marlowe, CC BY 4.0"),
    "medterm": src("Building a Medical Terminology Foundation", "https://ecampusontario.pressbooks.pub/medicalterminology/", "CC BY 4.0", CC_BY, "Kimberlee Carter and Marie Rutherford, CC BY 4.0"),
    "dle": src("Digital Literacy Essentials (University of Galway)", "https://openpress.universityofgalway.ie/digliteracyessentials/", "CC BY 4.0", CC_BY, "University of Galway Open Press, adapted from the Digital Citizenship Toolkit (Michelle Schwartz, ed.), CC BY 4.0"),
    "mt": src("Mastering Thinking (University of Southern Queensland)", "https://usq.pressbooks.pub/masteringthinking/", "CC BY-SA 4.0", CC_BY_SA, "University of Southern Queensland, CC BY-SA 4.0"),
    "lumen-fa": src("Financial Accounting (Lumen Learning)", "https://content.one.lumenlearning.com/financialaccounting/", "CC BY 4.0", CC_BY, "Lumen Learning, CC BY 4.0"),
    "stats": src("Significant Statistics (Virginia Tech)", "https://pressbooks.lib.vt.edu/introstatistics/", "CC BY-SA 4.0", CC_BY_SA, "John Morgan Russell, Virginia Tech Libraries, adapted from OpenStax Introductory Statistics, CC BY-SA 4.0"),
    "blueprint": src("Blueprint for Success in College and Career", "https://press.rebus.community/blueprint2/", "CC BY 4.0", CC_BY, "Dave Dillon, Rebus Community, CC BY 4.0"),
    "l2l": src("Learning to Learn Online (KPU)", "https://kpu.pressbooks.pub/learningtolearnonline/", "CC BY-SA 4.0", CC_BY_SA, "Kwantlen Polytechnic University, CC BY-SA 4.0"),
    "ostx-biz": src("OpenStax · Introduction to Business (1st ed.)", "https://openstax.org/details/books/introduction-business", "CC BY 4.0", CC_BY, "Lawrence J. Gitman, Carl McDaniel, Amit Shah et al., OpenStax, CC BY 4.0"),
    # Public-sector sources
    "govuk-sm": src("GOV.UK Service Manual", "https://www.gov.uk/service-manual", "Open Government Licence v3.0", OGL, OGL_NOTE),
    "govuk": src("GOV.UK guidance", "https://www.gov.uk/", "Open Government Licence v3.0", OGL, OGL_NOTE),
    "analysis-fn": src("UK Government Analysis Function guidance", "https://analysisfunction.civilservice.gov.uk/policy-store/", "Open Government Licence v3.0", OGL, OGL_NOTE),
    "eu": src("European Commission", "https://commission.europa.eu/", "CC BY 4.0", CC_BY, "© European Union, reused under CC BY 4.0 (Commission Decision 2011/833/EU)"),
    "eia": pd("U.S. EIA · Energy Explained", "https://www.eia.gov/energyexplained/", "U.S. Energy Information Administration"),
    "doe": pd("U.S. Department of Energy", "https://www.energy.gov/", "U.S. Department of Energy"),
    "afdc": pd("Alternative Fuels Data Center (U.S. DOE)", "https://afdc.energy.gov/", "U.S. Department of Energy, Alternative Fuels Data Center"),
    "osha": pd("OSHA (U.S. Department of Labor)", "https://www.osha.gov/", "Occupational Safety and Health Administration"),
    "healthit": pd("HealthIT.gov (ASTP/ONC, HHS)", "https://healthit.gov/", "U.S. Department of Health and Human Services"),
    "irs": pd("IRS Publication 583", "https://www.irs.gov/publications/p583", "Internal Revenue Service"),
    "digitalgov": pd("Digital.gov (U.S. GSA)", "https://digital.gov/guides/", "U.S. General Services Administration"),
    "nist": pd("NIST AI Risk Management Framework", "https://airc.nist.gov/airmf-resources/airmf/", "National Institute of Standards and Technology"),
    "epa": pd("U.S. Environmental Protection Agency", "https://www.epa.gov/", "U.S. Environmental Protection Agency"),
    "nasa": pd("NASA Earthdata", "https://www.earthdata.nasa.gov/learn", "NASA"),
}

GENAI = "microsoft/generative-ai-for-beginners"
ML = "microsoft/ML-For-Beginners"
DS = "microsoft/Data-Science-For-Beginners"
AI = "microsoft/AI-For-Beginners"
WEB = "microsoft/Web-Dev-For-Beginners"
IOT = "microsoft/IoT-For-Beginners"
SEC = "microsoft/Security-101"
AGENTS = "microsoft/ai-agents-for-beginners"
PA = "MicrosoftDocs/power-automate-docs"
ARCH = "MicrosoftDocs/architecture-center"
DAIR = "dair-ai/Prompt-Engineering-Guide"

# Open quiz banks that ship with the Microsoft curricula. ML/AI/Web lesson READMEs have stale quiz links, so those
# lessons name their post-lecture quiz id explicitly; DS and IoT links are reliable and are read from the README.
BANKS = {
    "ml": {"repo": ML, "files": ["quiz-app/src/assets/translations/en.json"], "source": "ms-ml"},
    "ai": {"repo": AI, "files": [f"etc/quiz-app/src/assets/translations/en/lesson-{i}.json" for i in range(1, 25)], "source": "ms-ai"},
    "web": {"repo": WEB, "files": ["quiz-app/src/assets/translations/en.json"], "source": "ms-web"},
    "ds": {"repo": DS, "files": [f"quiz-app/src/assets/translations/en/group-{i}.json" for i in range(1, 7)], "source": "ms-ds", "links_reliable": True},
    "iot": {"repo": IOT, "files": ["quiz-app/src/assets/translations/en.json"], "source": "ms-iot", "links_reliable": True},
}
REPO_BANK = {ML: "ml", AI: "ai", WEB: "web", DS: "ds", IOT: "iot"}

PM = "opentextbc.ca/projectmanagement"
GD = "opentextbc.ca/graphicdesign"
TOUR = "opentextbc.ca/introtourism2e"
EXCEL = "openoregon.pressbooks.pub/beginningexcel19"
FINSTRAT = "ecampusontario.pressbooks.pub/financialstrategy"
MEDTERM = "ecampusontario.pressbooks.pub/medicalterminology"
DLE = "openpress.universityofgalway.ie/digliteracyessentials"
MT = "usq.pressbooks.pub/masteringthinking"
LFA = "content.one.lumenlearning.com/financialaccounting"
STATS = "pressbooks.lib.vt.edu/introstatistics"
BLUEPRINT = "press.rebus.community/blueprint2"
L2L = "kpu.pressbooks.pub/learningtolearnonline"

EIA_SEL = ("div.l-col.article-content",)
GOOGLE_SEL = (".devsite-article-body", "main article")


def gh(repo, path, flavor="plain", **kw):
    return {"kind": "gh", "repo": repo, "path": path, "flavor": flavor, **kw}


def carp(repo, episode, **kw):
    return gh(repo, f"episodes/{episode}", "carpentries", **kw)


def html(url, select=None, **kw):
    return {"kind": "html", "url": url, **({"select": select} if select else {}), **kw}


def govuk(path, **kw):
    return {"kind": "govuk", "path": path, **kw}


def sm(path, **kw):
    return govuk(f"/service-manual/{path}", source="govuk-sm", **kw)


def pb(book, slug, **kw):
    return {"kind": "pressbooks", "book": book, "slug": slug, **kw}


def biz(page, **kw):
    return {"kind": "openstax", "book": "introduction-business", "page": page, "source": "ostx-biz", **kw}


def eia(path, **kw):
    return html(f"https://www.eia.gov/energyexplained/{path}", EIA_SEL, source="eia", **kw)


def doe(path, **kw):
    return html(f"https://www.energy.gov/cmei/systems/{path}", source="doe", **kw)


def afdc(path, **kw):
    return html(f"https://afdc.energy.gov/{path}", ("main",), source="afdc", **kw)


def lec(chapter, title, **kw):
    return html(f"https://www.ibiblio.org/kuphaldt/electricCircuits/DC/DC_{chapter}.html", ("body",), source="lec", title=title,
                drop_headings=(r"^Lessons In Electric Circuits", r"^Chapter \d+$", r"^Contributors$"), **kw)


def mod(title, *lessons, source=None):
    return {"title": title, "lessons": list(lessons), **({"source": source} if source else {})}


def stitch(title, *parts, **kw):
    return {"title": title, "parts": list(parts), **kw}


def split(target=1600, **kw):
    return {"target": target, **kw}


COURSES = {
    # ================================================================== AI & Data
    "python": {
        "title": "Python for Data", "subtitle": "Program in Python, load tables of data and make your first charts.",
        "level": "Beginner", "source": "swc-python",
        "outcomes": ["Write and run Python programs in notebooks", "Load and explore spreadsheets of data with pandas",
                     "Plot data with Matplotlib", "Automate repetitive work with loops, conditionals and functions"],
        "modules": [
            mod("Python basics", *(carp("swcarpentry/python-novice-gapminder", e) for e in
                                   ["01-run-quit.md", "02-variables.md", "03-types-conversion.md", "04-built-in.md"])),
            mod("Working with data", *(carp("swcarpentry/python-novice-gapminder", e) for e in
                                       ["06-libraries.md", "07-reading-tabular.md", "08-data-frames.md", "09-plotting.md"])),
            mod("Repeating and deciding", *(carp("swcarpentry/python-novice-gapminder", e) for e in
                                            ["11-lists.md", "12-for-loops.md", "13-conditionals.md", "14-looping-data-sets.md"])),
            mod("Writing reusable code", *(carp("swcarpentry/python-novice-gapminder", e) for e in
                                           ["16-writing-functions.md", "17-scope.md", "18-style.md"])),
        ],
    },
    "sql": {
        "title": "Databases and SQL", "subtitle": "Ask questions of real data with SQL — selecting, filtering, aggregating and joining.",
        "level": "Beginner", "source": "swc-sql",
        "outcomes": ["Explain how relational databases store data", "Select, sort and filter records with SQL",
                     "Aggregate and combine tables with joins", "Keep data clean and create your own tables"],
        "modules": [
            mod("Querying data", *(carp("swcarpentry/sql-novice-survey", e) for e in
                                   ["01-select.md", "02-sort-dup.md", "03-filter.md", "04-calc.md", "05-null.md"])),
            mod("Summarising and combining", *(carp("swcarpentry/sql-novice-survey", e) for e in ["06-agg.md", "07-join.md"])),
            mod("Designing data", *(carp("swcarpentry/sql-novice-survey", e) for e in ["08-hygiene.md", "09-create.md"])),
            mod("Where databases fit", gh(DS, "2-Working-With-Data/05-relational-databases/README.md", source="ms-ds"),
                gh(DS, "2-Working-With-Data/06-non-relational/README.md", source="ms-ds")),
        ],
    },
    "data_analysis": {
        "title": "Data Analysis Foundations", "subtitle": "From raw data to insights: defining, preparing, analysing and communicating data.",
        "level": "Beginner", "source": "ms-ds",
        "outcomes": ["Describe what data science is and the types of data", "Prepare and clean messy datasets with pandas",
                     "Follow the data science lifecycle from question to analysis", "Communicate findings so people act on them"],
        "modules": [
            mod("Understanding data", gh(DS, "1-Introduction/01-defining-data-science/README.md"), gh(DS, "1-Introduction/03-defining-data/README.md"),
                gh(DS, "1-Introduction/04-stats-and-probability/README.md")),
            mod("Working with data", gh(DS, "2-Working-With-Data/07-python/README.md"), gh(DS, "2-Working-With-Data/08-data-preparation/README.md"),
                carp("datacarpentry/openrefine-socialsci", "01-introduction.md", source="dc-openrefine"),
                carp("datacarpentry/openrefine-socialsci", "03-filter-sort.md", source="dc-openrefine")),
            mod("The data science lifecycle", gh(DS, "4-Data-Science-Lifecycle/14-Introduction/README.md"),
                gh(DS, "4-Data-Science-Lifecycle/15-analyzing/README.md"), gh(DS, "4-Data-Science-Lifecycle/16-communication/README.md")),
            mod("Data science in the world", gh(DS, "6-Data-Science-In-Wild/README.md")),
        ],
    },
    "data_viz": {
        "title": "Data Visualisation", "subtitle": "Choose and build the right chart, then design it so people read it correctly.",
        "level": "Beginner", "source": "ms-ds",
        "outcomes": ["Pick a chart type that fits your data and message", "Visualise quantities, distributions, proportions and relationships",
                     "Use colour, labels and tables accessibly", "Design honest, meaningful visualisations"],
        "modules": [
            mod("Charts for every question", gh(DS, "3-Data-Visualization/09-visualization-quantities/README.md"),
                gh(DS, "3-Data-Visualization/10-visualization-distributions/README.md"),
                gh(DS, "3-Data-Visualization/11-visualization-proportions/README.md"),
                gh(DS, "3-Data-Visualization/12-visualization-relationships/README.md")),
            mod("Telling the story", gh(DS, "3-Data-Visualization/13-meaningful-visualizations/README.md")),
            mod("Design guidance from government analysts",
                html("https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-charts/", source="analysis-fn", split=split(1800)),
                html("https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-colours-in-charts/", source="analysis-fn", split=split(1800, take=[0, 1, 2])),
                html("https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-tables/", source="analysis-fn", split=split(1800))),
        ],
    },
    "statistics": {
        "title": "Statistics Fundamentals", "subtitle": "Describe data, reason with probability and draw sound conclusions from samples.",
        "level": "Beginner", "source": "stats",
        "outcomes": ["Collect data with sound sampling and study design", "Summarise data with tables, graphs, centre and spread",
                     "Use probability and the normal distribution", "Build confidence intervals, run hypothesis tests and fit a regression line"],
        "modules": [
            mod("Data and sampling", *(pb(STATS, s) for s in ["introduction", "types-of-data", "observational-studies", "experimental-design-and-ethics",
                                                               "data-sampling-and-variation-in-data-and-sampling"])),
            mod("Describing data", *(pb(STATS, s) for s in ["frequency-frequency-tables-and-levels-of-measurement", "displaying-categorical-data",
                                                             "histograms-frequency-polygons-and-time-series-graphs", "measures-of-the-center-of-the-data",
                                                             "measures-of-the-spread-of-the-data", "measures-of-the-location-of-the-data"])),
            mod("Probability and distributions", *(pb(STATS, s) for s in ["terminology", "compound-events", "binomial-distribution", "introduction-18"])),
            mod("Inference", *(pb(STATS, s) for s in ["introduction-19", "the-central-limit-theorem-for-sample-means-averages", "introduction-20",
                                                       "null-and-alternative-hypotheses", "outcomes-and-the-type-i-and-type-ii-errors"])),
            mod("Relationships between variables", *(pb(STATS, s) for s in ["scatter-plots", "measures-of-association", "the-regression-equation", "outliers"])),
        ],
    },
    "machine_learning": {
        "title": "Machine Learning for Beginners", "subtitle": "Classic machine learning with Python and scikit-learn — regression, classification and clustering.",
        "level": "Intermediate", "source": "ms-ml",
        "outcomes": ["Explain what machine learning is and where it is used", "Build regression models and evaluate them",
                     "Train classifiers and compare them", "Find groups in data with clustering, and apply ML responsibly"],
        "quiz": {"per_lesson": 1},
        "modules": [
            mod("Introduction", gh(ML, "1-Introduction/1-intro-to-ML/README.md", quiz=2), gh(ML, "1-Introduction/2-history-of-ML/README.md", quiz=4),
                gh(ML, "1-Introduction/3-fairness/README.md", quiz=6), gh(ML, "1-Introduction/4-techniques-of-ML/README.md", quiz=8)),
            mod("Regression", gh(ML, "2-Regression/1-Tools/README.md", quiz=10), gh(ML, "2-Regression/2-Data/README.md", quiz=12),
                gh(ML, "2-Regression/3-Linear/README.md", quiz=14), gh(ML, "2-Regression/4-Logistic/README.md", quiz=16)),
            mod("Classification", gh(ML, "4-Classification/1-Introduction/README.md", quiz=20), gh(ML, "4-Classification/2-Classifiers-1/README.md", quiz=22),
                gh(ML, "4-Classification/3-Classifiers-2/README.md", quiz=24)),
            mod("Clustering", gh(ML, "5-Clustering/1-Visualize/README.md", quiz=28), gh(ML, "5-Clustering/2-K-Means/README.md", quiz=30)),
            mod("ML in the real world", gh(ML, "9-Real-World/1-Applications/README.md", quiz=50)),
        ],
    },
    "genai_apps": {
        "title": "Building Generative AI Applications", "subtitle": "Large language models, chat and search apps, RAG, function calling and AI agents.",
        "level": "Intermediate", "source": "ms-genai",
        "outcomes": ["Explain how large language models work and compare them", "Build text-generation, chat and search applications",
                     "Ground answers in your own data with RAG", "Design AI agents that use tools"],
        "modules": [
            mod("Foundations", gh(GENAI, "01-introduction-to-genai/README.md"), gh(GENAI, "02-exploring-and-comparing-different-llms/README.md")),
            mod("Building apps", gh(GENAI, "06-text-generation-apps/README.md"), gh(GENAI, "07-building-chat-applications/README.md"),
                gh(GENAI, "08-building-search-applications/README.md"), gh(GENAI, "11-integrating-with-function-calling/README.md"),
                gh(GENAI, "12-designing-ux-for-ai-applications/README.md")),
            mod("Grounding and customising", gh(GENAI, "15-rag-and-vector-databases/README.md"), gh(GENAI, "16-open-source-models/README.md"),
                gh(GENAI, "18-fine-tuning/README.md"), gh(GENAI, "19-slm/README.md")),
            mod("AI agents", gh(AGENTS, "01-intro-to-ai-agents/README.md", source="ms-agents"),
                gh(AGENTS, "03-agentic-design-patterns/README.md", source="ms-agents"), gh(AGENTS, "04-tool-use/README.md", source="ms-agents"),
                gh(AGENTS, "05-agentic-rag/README.md", source="ms-agents")),
        ],
    },
    "prompt_eng": {
        "title": "Prompt Engineering & AI Tools at Work", "subtitle": "Write prompts that get reliable results — and know when not to trust the answer.",
        "level": "Beginner", "source": "dair",
        "outcomes": ["Structure prompts with instructions, context, input and output format", "Use zero-shot, few-shot and chain-of-thought prompting",
                     "Chain prompts for multi-step work", "Recognise hallucinations, bias and prompt injection"],
        "modules": [
            mod("Prompting fundamentals", gh(GENAI, "04-prompt-engineering-fundamentals/README.md", source="ms-genai"),
                gh(DAIR, "pages/introduction/basics.en.mdx", "mdx", title="Basics of Prompting"),
                gh(DAIR, "pages/introduction/settings.en.mdx", "mdx", title="LLM Settings"),
                gh(DAIR, "pages/introduction/elements.en.mdx", "mdx", title="Elements of a Prompt"),
                gh(DAIR, "pages/introduction/tips.en.mdx", "mdx", title="General Tips for Designing Prompts"),
                gh(DAIR, "pages/introduction/examples.en.mdx", "mdx", title="Examples of Prompts")),
            mod("Prompting techniques", gh(GENAI, "05-advanced-prompts/README.md", source="ms-genai"),
                gh(DAIR, "pages/techniques/zeroshot.en.mdx", "mdx", title="Zero-Shot Prompting"),
                gh(DAIR, "pages/techniques/fewshot.en.mdx", "mdx", title="Few-Shot Prompting"),
                gh(DAIR, "pages/techniques/cot.en.mdx", "mdx", title="Chain-of-Thought Prompting"),
                gh(DAIR, "pages/techniques/prompt_chaining.en.mdx", "mdx", title="Prompt Chaining")),
            mod("Risks and responsible use", gh(DAIR, "pages/risks/factuality.en.mdx", "mdx", title="Factuality"),
                gh(DAIR, "pages/risks/biases.en.mdx", "mdx", title="Biases"),
                gh(DAIR, "pages/risks/adversarial.en.mdx", "mdx", title="Adversarial Prompting and Prompt Injection")),
        ],
    },
    "mlops": {
        "title": "MLOps & Model Deployment", "subtitle": "Take models from a notebook to a reliable production system — and keep them healthy.",
        "level": "Intermediate", "source": "google-ml",
        "outcomes": ["Serve a trained model from a web application", "Choose static or dynamic training and inference",
                     "Test, deploy and monitor ML pipelines", "Automate training and delivery with MLOps maturity levels"],
        "modules": [
            mod("From notebook to product", gh(ML, "3-Web-App/1-Web-App/README.md", source="ms-ml", quiz=18),
                gh(GENAI, "14-the-generative-ai-application-lifecycle/README.md", source="ms-genai")),
            mod("Production ML systems",
                html("https://developers.google.com/machine-learning/crash-course/production-ml-systems/static-vs-dynamic-training", GOOGLE_SEL, title="Static versus dynamic training"),
                html("https://developers.google.com/machine-learning/crash-course/production-ml-systems/static-vs-dynamic-inference", GOOGLE_SEL, title="Static versus dynamic inference"),
                html("https://developers.google.com/machine-learning/crash-course/production-ml-systems/deployment-testing", GOOGLE_SEL, title="Deployment testing"),
                html("https://developers.google.com/machine-learning/crash-course/production-ml-systems/monitoring", GOOGLE_SEL, title="Monitoring pipelines")),
            mod("Automating ML delivery",
                html("https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning", GOOGLE_SEL,
                     source="google-cloud", title="MLOps: continuous delivery and automation pipelines", split=split(1500))),
            mod("Rules of machine learning",
                html("https://developers.google.com/machine-learning/guides/rules-of-ml", GOOGLE_SEL, title="Rules of Machine Learning", split=split(1800))),
            mod("Shipping with containers", carp("carpentries-incubator/docker-introduction", "running-containers.md", source="ci-docker"),
                carp("carpentries-incubator/docker-introduction", "creating-container-images.md", source="ci-docker")),
        ],
    },
    "data_engineering": {
        "title": "Data Engineering & Pipelines", "subtitle": "Store, move and transform data reliably — databases, ETL, batch and streaming.",
        "level": "Intermediate", "source": "azure-arch",
        "outcomes": ["Choose between relational, non-relational and analytical data stores", "Design ETL and ELT pipelines",
                     "Explain batch and stream processing architectures", "Clean and transform data with repeatable steps"],
        "modules": [
            mod("Data stores", gh(DS, "2-Working-With-Data/05-relational-databases/README.md", source="ms-ds"),
                gh(DS, "2-Working-With-Data/06-non-relational/README.md", source="ms-ds"),
                gh(ARCH, "docs/data-guide/technology-choices/understand-data-store-models.md", "docfx"),
                gh(ARCH, "docs/data-guide/relational-data/online-transaction-processing.md", "docfx"),
                gh(ARCH, "docs/data-guide/relational-data/online-analytical-processing.md", "docfx")),
            mod("Moving and transforming data", gh(ARCH, "docs/data-guide/relational-data/etl-content.md", "docfx", title="Extract, transform, load (ETL)"),
                gh(ARCH, "docs/data-guide/technology-choices/pipeline-orchestration-data-movement.md", "docfx"),
                gh(ARCH, "docs/data-guide/scenarios/data-lake.md", "docfx")),
            mod("Big data processing", gh(ARCH, "docs/guide/architecture-styles/big-data.md", "docfx"),
                gh(ARCH, "docs/data-guide/technology-choices/batch-processing.md", "docfx"),
                gh(ARCH, "docs/data-guide/technology-choices/stream-processing.md", "docfx")),
            mod("Repeatable data cleaning", *(carp("datacarpentry/openrefine-socialsci", e, source="dc-openrefine") for e in
                                              ["02-working-with-openrefine.md", "04-numbers.md", "05-scripts.md"])),
        ],
    },
    "ai_governance": {
        "title": "Responsible AI & AI Governance", "subtitle": "Identify, measure and manage AI risks — fairness, transparency, accountability and safety.",
        "level": "Intermediate", "source": "nist",
        "outcomes": ["Explain the principles of responsible AI", "Recognise and mitigate bias in data and models",
                     "Apply the NIST AI Risk Management Framework", "Put data and AI ethics into practice in a project"],
        "modules": [
            mod("Why responsible AI", gh(GENAI, "03-using-generative-ai-responsibly/README.md", source="ms-genai"),
                gh(ML, "1-Introduction/3-fairness/README.md", source="ms-ml", quiz=6), gh(DS, "1-Introduction/02-ethics/README.md", source="ms-ds")),
            mod("Bias and fairness",
                stitch("Types of bias and how to mitigate them",
                       html("https://developers.google.com/machine-learning/crash-course/fairness/types-of-bias", GOOGLE_SEL, title="Types of bias"),
                       html("https://developers.google.com/machine-learning/crash-course/fairness/evaluating-for-bias", GOOGLE_SEL, title="Evaluating for bias"),
                       html("https://developers.google.com/machine-learning/crash-course/fairness/mitigating-bias", GOOGLE_SEL, title="Mitigating bias"),
                       source="google-ml")),
            mod("The NIST AI Risk Management Framework",
                html("https://airc.nist.gov/airmf-resources/airmf/1-sec-risk/", ("#main-content",), title="Framing AI risk"),
                html("https://airc.nist.gov/airmf-resources/airmf/3-sec-characteristics/", ("#main-content",), title="AI risks and trustworthiness"),
                html("https://airc.nist.gov/airmf-resources/airmf/5-sec-core/", ("#main-content",), title="The AI RMF Core: govern, map, measure, manage", split=split(2200)),
                html("https://airc.nist.gov/airmf-resources/airmf/appendices/app-b-how-ai-risks-differ-from-traditional-software-risks/", ("#main-content",),
                     title="How AI risks differ from traditional software risks")),
            mod("Ethics in practice",
                govuk("/government/publications/data-ethics-framework/data-and-ai-ethics-framework", source="govuk", split=split(2000, take=[0, 1, 2, 3, 4]))),
            mod("Securing AI", gh(SEC, "8.1 AI security key concepts.md", source="ms-sec"), gh(SEC, "8.3 Responsible AI.md", source="ms-sec")),
        ],
    },
    "computer_vision": {
        "title": "Computer Vision", "subtitle": "How computers see: image processing, convolutional networks, transfer learning, detection and segmentation.",
        "level": "Intermediate", "source": "ms-ai",
        "outcomes": ["Process images and understand pixels and features", "Explain how convolutional neural networks work",
                     "Reuse pre-trained models with transfer learning", "Detect objects and check product quality with vision models"],
        "modules": [
            mod("Seeing with computers", gh(AI, "lessons/4-ComputerVision/06-IntroCV/README.md", quiz=206),
                gh(AI, "lessons/4-ComputerVision/07-ConvNets/README.md", quiz=207)),
            mod("Using deep learning", gh(AI, "lessons/4-ComputerVision/08-TransferLearning/README.md", quiz=208),
                gh(AI, "lessons/4-ComputerVision/09-Autoencoders/README.md", quiz=209)),
            mod("Detection and segmentation", gh(AI, "lessons/4-ComputerVision/11-ObjectDetection/README.md", quiz=211),
                gh(AI, "lessons/4-ComputerVision/12-Segmentation/README.md", quiz=212)),
            mod("Vision in industry", gh(IOT, "4-manufacturing/lessons/1-train-fruit-detector/README.md", source="ms-iot"),
                gh(IOT, "4-manufacturing/lessons/2-check-fruit-from-device/README.md", source="ms-iot"),
                gh(IOT, "5-retail/lessons/1-train-stock-detector/README.md", source="ms-iot")),
        ],
    },
    "excel": {
        "title": "Spreadsheets with Excel", "subtitle": "Enter, format and analyse data; write formulas and functions; build charts and tables.",
        "level": "Beginner", "source": "excel",
        "outcomes": ["Enter, edit and format data professionally", "Write formulas with relative and absolute references",
                     "Use statistical, logical, lookup and finance functions", "Present data with charts, tables and conditional formatting"],
        "modules": [
            mod("Fundamental skills", *(pb(EXCEL, s) for s in ["1-1-overview-of-microsoft-excel", "1-2-entering-editing-and-managing-data",
                                                                "1-3-formatting-and-data-analysis"])),
            mod("Formulas and functions", *(pb(EXCEL, s) for s in ["2-1-formulas", "2-2-statistical-functions", "2-3-functions-for-personal-finance",
                                                                    "3-1-more-on-formulas-and-functions", "3-2-logical-and-lookup-functions",
                                                                    "3-3-conditional-formatting"])),
            mod("Presenting data", *(pb(EXCEL, s) for s in ["4-1-choosing-a-chart-type", "4-2-formatting-charts", "5-1-table-basics",
                                                             "5-2-intermediate-table-skills"])),
            mod("Working across sheets", *(pb(EXCEL, s) for s in ["6-1-multiple-sheet-basics", "6-2-formulas-with-3-d-references", "6-3-templates"])),
        ],
    },
    # ================================================================== Digital & Tech
    "digital_literacy": {
        "title": "Digital Literacy Essentials", "subtitle": "Communicate, find and judge information, stay safe and take part confidently online.",
        "level": "Beginner", "source": "dle",
        "outcomes": ["Describe the essential digital skills for life and work", "Choose the right mode of digital communication",
                     "Evaluate online information and sources critically", "Act as a safe, responsible digital citizen"],
        "modules": [
            mod("What digital skills are", govuk("/government/publications/essential-digital-skills-framework/essential-digital-skills-framework", source="govuk"),
                pb(DLE, "chapter-1")),
            mod("Communicating online", pb(DLE, "chapter-2-modes-of-digital-communication", split=split(1800))),
            mod("Digital citizenship", pb(DLE, "chapter-3-digital-citizenship", split=split(1800))),
            mod("Thinking critically online", pb(DLE, "chapter-4-critical-approaches-to-digital-literad", split=split(1800)),
                pb(DLE, "chapter-5-developing-evaluative-literacy-skills", split=split(1800))),
            mod("Staying safe", gh(SEC, "1.2 Common cybersecurity threats.md", source="ms-sec"), pb(DLE, "chapter-6-joining-the-digital-conversation")),
        ],
    },
    "software_dev": {
        "title": "Web Development for Beginners", "subtitle": "Programming basics, Git and GitHub, accessibility, JavaScript, HTML and CSS — by building real projects.",
        "level": "Beginner", "source": "ms-web",
        "outcomes": ["Understand programming languages and developer tools", "Track and share code with Git and GitHub",
                     "Write JavaScript with variables, functions, decisions and loops", "Build accessible web pages with HTML and CSS"],
        "quiz": {"per_lesson": 1},
        "modules": [
            mod("Getting started", gh(WEB, "1-getting-started-lessons/1-intro-to-programming-languages/README.md", quiz=2),
                gh(WEB, "1-getting-started-lessons/2-github-basics/README.md", quiz=4), gh(WEB, "1-getting-started-lessons/3-accessibility/README.md", quiz=6)),
            mod("JavaScript basics", gh(WEB, "2-js-basics/1-data-types/README.md", quiz=8), gh(WEB, "2-js-basics/2-functions-methods/README.md", quiz=10),
                gh(WEB, "2-js-basics/3-making-decisions/README.md", quiz=12), gh(WEB, "2-js-basics/4-arrays-loops/README.md", quiz=14)),
            mod("HTML, CSS and the DOM", gh(WEB, "3-terrarium/1-intro-to-html/README.md", quiz=16), gh(WEB, "3-terrarium/2-intro-to-css/README.md", quiz=18),
                gh(WEB, "3-terrarium/3-intro-to-DOM-and-closures/README.md", quiz=20)),
            mod("Version control with Git", *(carp("swcarpentry/git-novice", e, source="swc-git") for e in
                                              ["01-basics.md", "03-create.md", "04-changes.md", "05-history.md", "07-github.md", "08-collab.md", "09-conflict.md"])),
        ],
    },
    "cloud_devops": {
        "title": "Cloud & DevOps", "subtitle": "Run software in the cloud: containers, hosting, continuous deployment and monitoring.",
        "level": "Beginner", "source": "ci-docker",
        "outcomes": ["Explain cloud computing and its service models", "Package and run software in containers",
                     "Deploy software regularly and safely", "Keep services secure, monitored and available"],
        "modules": [
            mod("The cloud", gh(DS, "5-Data-Science-In-Cloud/17-Introduction/README.md", source="ms-ds"),
                sm("technology/deciding-how-to-host-your-service")),
            mod("Containers", *(carp("carpentries-incubator/docker-introduction", e) for e in
                                ["introduction.md", "running-containers.md", "managing-containers.md", "docker-hub.md", "creating-container-images.md"])),
            mod("Delivering continuously", sm("technology/maintaining-version-control-in-coding"), sm("technology/deploying-software-regularly"),
                sm("technology/manage-your-software-configuration"), sm("technology/quality-assurance-testing-your-service-regularly")),
            mod("Running services", sm("technology/monitoring-the-status-of-your-service"), sm("technology/uptime-and-availability-keeping-your-service-online"),
                sm("technology/securing-your-cloud-environment")),
        ],
    },
    "linux_networking": {
        "title": "Linux Command Line & Networking", "subtitle": "Work confidently in the shell and understand how networks connect computers.",
        "level": "Beginner", "source": "swc-shell",
        "outcomes": ["Navigate files and directories from the command line", "Combine commands with pipes and filters",
                     "Automate tasks with loops and shell scripts", "Explain key networking and network-security concepts"],
        "modules": [
            mod("The Unix shell", *(carp("swcarpentry/shell-novice", e) for e in ["01-intro.md", "02-filedir.md", "03-create.md", "04-pipefilter.md"])),
            mod("Automating work", *(carp("swcarpentry/shell-novice", e) for e in ["05-loop.md", "06-script.md", "07-find.md"])),
            mod("Networking", gh(SEC, "3.1 Networking key concepts.md", source="ms-sec"), gh(SEC, "3.2 Networking zero trust architecture.md", source="ms-sec"),
                gh(SEC, "3.3 Network security capabilities.md", source="ms-sec"), sm("technology/using-https")),
        ],
    },
    "cybersecurity": {
        "title": "Cybersecurity Fundamentals", "subtitle": "Core security concepts: threats, risk, identity, networks, operations, applications, data and AI.",
        "level": "Beginner", "source": "ms-sec",
        "outcomes": ["Explain the CIA triad and common cyber threats", "Manage risk and apply zero trust",
                     "Protect identities, networks and infrastructure", "Understand security operations, application, data and AI security"],
        "modules": [
            mod("Security foundations", *(gh(SEC, f"{n}.md") for n in ["1.1 The CIA triad and other key concepts", "1.2 Common cybersecurity threats",
                                                                        "1.3 Understanding risk management", "1.4 Security practices and documentation",
                                                                        "1.5 Zero trust", "1.6 Shared responsibility model"])),
            mod("Identity and access", *(gh(SEC, f"{n}.md") for n in ["2.1 IAM key concepts", "2.2 IAM zero trust architecture", "2.3 IAM capabilities"])),
            mod("Networks", *(gh(SEC, f"{n}.md") for n in ["3.1 Networking key concepts", "3.2 Networking zero trust architecture", "3.3 Network security capabilities"])),
            mod("Security operations", *(gh(SEC, f"{n}.md") for n in ["4.1 SecOps key concepts", "4.2 SecOps zero trust architecture", "4.3 SecOps capabilities"])),
            mod("Applications, infrastructure and data", *(gh(SEC, f"{n}.md") for n in ["5.1 AppSec key concepts", "5.2 AppSec key capabilities",
                                                                                         "6.1 Infrastructure security key concepts", "6.2 Infrastructure security capabilities",
                                                                                         "7.1 Data security key concepts", "7.2 Data security capabilities"])),
            mod("Securing AI", *(gh(SEC, f"{n}.md") for n in ["8.1 AI security key concepts", "8.2 AI security capabilities"])),
        ],
    },
    "ux_design": {
        "title": "User-Centred Design", "subtitle": "Research users, make sense of what you learn, design and test — with methods used by government digital teams.",
        "level": "Beginner", "source": "18f",
        "outcomes": ["Plan user research and run interviews and observation", "Synthesise research with affinity maps, personas and journey maps",
                     "Sketch flows, wireframes and prototypes", "Evaluate designs with usability tests and expert reviews"],
        "modules": [
            mod("Learning about users", sm("user-research/start-by-learning-user-needs"), sm("user-research/plan-user-research-for-your-service"),
                sm("user-research/using-in-depth-interviews"), sm("user-research/contextual-research-and-observation")),
            mod("Discover", stitch("Interviews and contextual inquiry", gh("18F/methods", "_methods/stakeholder-and-user-interviews.md"),
                                   gh("18F/methods", "_methods/contextual-inquiry.md"), gh("18F/methods", "_methods/recruiting.md")),
                stitch("Hopes, fears and five whys", gh("18F/methods", "_methods/hopes-and-fears.md"), gh("18F/methods", "_methods/five-whys.md"))),
            mod("Make sense of research", sm("user-research/analyse-a-research-session"),
                stitch("Affinity mapping and the KJ method", gh("18F/methods", "_methods/affinity-mapping.md"), gh("18F/methods", "_methods/kj-method.md")),
                stitch("Personas, journeys and mental models", gh("18F/methods", "_methods/personas.md"), gh("18F/methods", "_methods/journey-mapping.md"),
                       gh("18F/methods", "_methods/mental-modeling.md"), gh("18F/methods", "_methods/user-scenarios.md")),
                sm("user-research/creating-an-experience-map")),
            mod("Make", stitch("Structuring the experience", gh("18F/methods", "_methods/task-flow-analysis.md"), gh("18F/methods", "_methods/site-mapping.md"),
                               gh("18F/methods", "_methods/card-sorting.md")),
                stitch("Wireframes and prototypes", gh("18F/methods", "_methods/design-studio.md"), gh("18F/methods", "_methods/wireframing.md"),
                       gh("18F/methods", "_methods/prototyping.md"), gh("18F/methods", "_methods/style-tiles.md")),
                sm("design/making-prototypes"), sm("design/writing-for-user-interfaces")),
            mod("Validate", sm("user-research/using-moderated-usability-testing"),
                stitch("Testing with users", gh("18F/methods", "_methods/usability-testing.md"), gh("18F/methods", "_methods/visual-preference-testing.md"),
                       gh("18F/methods", "_methods/multivariate-testing.md")),
                stitch("Expert reviews", gh("18F/methods", "_methods/heuristic-evaluation.md"), gh("18F/methods", "_methods/cognitive-walkthrough.md"),
                       gh("18F/methods", "_methods/content-audit.md")),
                sm("helping-people-to-use-your-service/making-your-service-accessible-an-introduction")),
        ],
    },
    "process_automation": {
        "title": "Process Automation & RPA", "subtitle": "Plan, design, build and test business process automation — cloud flows, desktop RPA and process mining.",
        "level": "Beginner", "source": "ms-pa",
        "outcomes": ["Decide which processes to automate and how", "Design reliable automated processes",
                     "Choose between cloud flows, desktop RPA, attended and unattended bots", "Test, deploy and improve automations"],
        "modules": [
            mod("Automation basics", gh(PA, "articles/getting-started.md", "docfx"), gh(PA, "articles/flow-types.md", "docfx"),
                gh(PA, "articles/desktop-flows/introduction.md", "docfx"), gh(PA, "articles/process-mining-overview.md", "docfx")),
            mod("Planning an automation", *(gh(PA, f"articles/guidance/planning/{p}.md", "docfx") for p in
                                            ["introduction", "planning-phase", "various-types-process-automation", "determine-automation-methods",
                                             "attended-unattended"])),
            mod("Designing and delivering", *(gh(PA, f"articles/guidance/planning/{p}.md", "docfx") for p in
                                              ["process-design", "decision-making-flow", "making-phase", "testing-strategy", "deploy-to-production"])),
        ],
    },
    "iot_embedded": {
        "title": "IoT for Beginners", "subtitle": "Connect sensors and devices to the internet and turn physical signals into data.",
        "level": "Beginner", "source": "ms-iot",
        "outcomes": ["Explain what the Internet of Things is and how devices work", "Read sensors and control actuators",
                     "Connect devices to the internet and send telemetry", "Track, store and visualise location data"],
        "modules": [
            mod("Getting started", *(gh(IOT, f"1-getting-started/lessons/{d}/README.md") for d in
                                     ["1-introduction-to-iot", "2-deeper-dive", "3-sensors-and-actuators", "4-connect-internet"])),
            mod("Location tracking", *(gh(IOT, f"3-transport/lessons/{d}/README.md") for d in
                                       ["1-location-tracking", "2-store-location-data", "3-visualize-location-data", "4-geofences"])),
        ],
    },
    "digital_marketing": {
        "title": "Digital Marketing & Analytics", "subtitle": "Understand customers, promote products online, get found in search and measure what works.",
        "level": "Beginner", "source": "ostx-biz",
        "outcomes": ["Apply the marketing concept, segmentation and the marketing mix", "Plan promotion across advertising, PR and social media",
                     "Improve how a website appears in search results", "Set performance metrics and choose analytics tools"],
        "modules": [
            mod("Marketing foundations", biz("11-1-the-marketing-concept"), biz("11-2-creating-a-marketing-strategy"), biz("11-3-developing-a-marketing-mix"),
                stitch("Buyer behaviour and market segmentation", biz("11-4-buyer-behavior"), biz("11-5-market-segmentation"), source="ostx-biz")),
            mod("Promotion", biz("12-5-promotion-strategy"), biz("12-6-the-huge-impact-of-advertising"),
                stitch("Public relations and social media", biz("12-9-public-relations-helps-build-goodwill"), biz("12-10-trends-in-social-media"), source="ostx-biz"),
                biz("12-11-trends-in-e-commerce")),
            mod("Search and content",
                html("https://developers.google.com/search/docs/fundamentals/how-search-works", GOOGLE_SEL, source="google-search", title="How search engines work"),
                html("https://developers.google.com/search/docs/fundamentals/seo-starter-guide", GOOGLE_SEL, source="google-search", title="SEO starter guide", split=split(1500)),
                html("https://developers.google.com/search/docs/fundamentals/creating-helpful-content", GOOGLE_SEL, source="google-search", title="Creating helpful, people-first content")),
            mod("Measuring what works", sm("measuring-success/how-to-set-performance-metrics-for-your-service"),
                sm("measuring-success/choosing-digital-analytics-tools"), sm("measuring-success/measuring-completion-rate"),
                sm("helping-people-to-use-your-service/encouraging-people-to-use-your-digital-service")),
        ],
    },
    # ================================================================== Green & Energy
    "solar_pv": {
        "title": "Solar PV Systems", "subtitle": "How sunlight becomes electricity — cells, modules, system design, grid integration and going solar.",
        "level": "Beginner", "source": "doe",
        "outcomes": ["Explain solar radiation and how photovoltaic cells work", "Compare PV technologies and what limits their efficiency",
                     "Describe how PV systems are designed and connected to the grid", "Plan a solar installation and its end of life"],
        "modules": [
            mod("Solar energy basics", eia("solar/"), doe("how-does-solar-work", title="How does solar work?"), doe("solar-radiation-basics")),
            mod("Photovoltaic technology", eia("solar/photovoltaics-and-electricity.php"),
                stitch("PV technology and cells", doe("solar-photovoltaic-technology-basics"), doe("solar-photovoltaic-cell-basics"), source="doe"),
                doe("solar-photovoltaic-performance-and-efficiency-basics"), doe("solar-photovoltaic-manufacturing-basics")),
            mod("PV systems and the grid", doe("solar-photovoltaic-system-design-basics"), doe("photovoltaic-system-design-and-energy-yield"),
                doe("solar-integration-inverters-and-grid-services-basics")),
            mod("Going solar", doe("homeowners-guide-solar", split=split(1800)), eia("solar/where-solar-is-found.php"),
                doe("end-life-management-solar-photovoltaics")),
        ],
    },
    "energy_efficiency": {
        "title": "Energy Management & Efficiency", "subtitle": "Measure how energy is used, find savings with energy audits and act on them.",
        "level": "Beginner", "source": "eia",
        "outcomes": ["Convert between energy units and read energy data", "Explain how homes, commercial buildings and industry use energy",
                     "Run an energy audit that meets ESOS requirements", "Prioritise and track energy-saving measures"],
        "modules": [
            mod("Energy basics", eia("units-and-calculators/"), eia("use-of-energy/efficiency-and-conservation.php"), eia("electricity/")),
            mod("Where energy goes", eia("use-of-energy/homes.php"), eia("use-of-energy/commercial-buildings.php"), eia("use-of-energy/industry.php")),
            mod("Energy audits", govuk("/guidance/energy-savings-opportunity-scheme-esos", source="govuk", title="Energy audits under ESOS: an overview"),
                govuk("/government/publications/comply-with-the-energy-savings-opportunity-scheme-esos-phase-4/how-to-comply-with-the-energy-savings-opportunity-scheme-esos-phase-4",
                      source="govuk", split=split(2000)),
                govuk("/government/publications/comply-with-the-energy-savings-opportunity-scheme-esos-phase-4/appendix-c-advice-for-complying-with-esos", source="govuk")),
            mod("Saving energy in practice", govuk("/guidance/make-your-technology-sustainable", source="govuk"),
                govuk("/guidance/non-domestic-private-rented-property-minimum-energy-efficiency-standard-landlord-guidance", source="govuk", split=split(2000, take=[0, 1]))),
        ],
    },
    "esg_reporting": {
        "title": "ESG & Sustainability Reporting", "subtitle": "What companies must disclose about climate, environment and society — and how reports are prepared.",
        "level": "Intermediate", "source": "eu",
        "outcomes": ["Explain why and how companies report on sustainability", "Describe the EU CSRD, the EU taxonomy and UK SRS",
                     "Prepare streamlined energy and carbon disclosures", "Report on environmental impacts such as waste and resources"],
        "modules": [
            mod("Why sustainability reporting",
                html("https://finance.ec.europa.eu/financial-markets/company-reporting-and-auditing/company-reporting/corporate-sustainability-reporting_en",
                     ("main article", "#main-content"), title="Corporate sustainability reporting in the EU"),
                html("https://finance.ec.europa.eu/sustainable-finance/tools-and-standards/eu-taxonomy-sustainable-activities_en", ("main article", "#main-content"),
                     title="The EU taxonomy for sustainable activities"),
                govuk("/guidance/uk-sustainability-reporting-standards", source="govuk")),
            mod("Energy and carbon disclosures",
                govuk("/government/publications/streamlined-energy-and-carbon-reporting-secr-for-academy-trusts/streamlined-energy-and-carbon-reporting-secr-for-academy-trusts",
                      source="govuk", title="Streamlined Energy and Carbon Reporting (SECR) in practice", split=split(1400))),
            mod("Environmental impacts", govuk("/government/publications/resources-and-waste-strategy-for-england/resources-and-waste-strategy-at-a-glance", source="govuk"),
                sm("design/environmentally-sustainable-services"), govuk("/guidance/make-your-technology-sustainable", source="govuk")),
            mod("Responsible data and AI", govuk("/government/publications/data-ethics-framework/data-and-ai-ethics-framework", source="govuk", split=split(2200, take=[0, 1]))),
        ],
    },
    "carbon_accounting": {
        "title": "Carbon (GHG) Accounting", "subtitle": "Measure an organisation's greenhouse gas emissions across scopes 1, 2 and 3 and report them credibly.",
        "level": "Intermediate", "source": "epa",
        "outcomes": ["Explain greenhouse gases and where emissions come from", "Draw organisational boundaries and classify scope 1, 2 and 3 emissions",
                     "Calculate emissions with activity data and emission factors", "Report emissions and intensity ratios under SECR"],
        "modules": [
            mod("Greenhouse gases", eia("energy-and-the-environment/greenhouse-gases.php"), eia("energy-and-the-environment/where-greenhouse-gases-come-from.php")),
            mod("Building an inventory",
                html("https://www.epa.gov/climateleadership/ghg-inventory-development-process-and-guidance", ("main article", "article"), title="The GHG inventory development process"),
                html("https://www.epa.gov/climateleadership/scope-1-and-scope-2-inventory-guidance", ("main article", "article"), title="Scope 1 and scope 2 emissions"),
                html("https://www.epa.gov/climateleadership/scope-3-inventory-guidance", ("main article", "article"), title="Scope 3 emissions")),
            mod("Calculating emissions",
                html("https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator-calculations-and-references", ("main article", "article"),
                     title="Emission factors and calculations", split=split(1800, take=[0, 1, 2])),
                govuk("/guidance/sharing-information-on-greenhouse-gas-emissions-from-local-authority-own-estate-and-operations-previously-ni-185",
                      source="govuk", title="Measuring an organisation's own emissions")),
            mod("Reporting", govuk("/government/publications/streamlined-energy-and-carbon-reporting-secr-for-academy-trusts/streamlined-energy-and-carbon-reporting-secr-for-academy-trusts",
                                   source="govuk", title="Streamlined Energy and Carbon Reporting (SECR)", split=split(1400))),
        ],
    },
    "ev_tech": {
        "title": "Electric Vehicles & Batteries", "subtitle": "How electric vehicles, batteries and charging work — and how to maintain and deploy them safely.",
        "level": "Beginner", "source": "afdc",
        "outcomes": ["Explain how all-electric and plug-in hybrid vehicles work", "Describe battery types, chemistry and lifespan",
                     "Plan home, workplace and public charging", "Maintain EVs safely and assess their benefits and emissions"],
        "modules": [
            mod("How electric vehicles work",
                stitch("All-electric and plug-in hybrid vehicles", afdc("vehicles/how-do-all-electric-cars-work"), afdc("vehicles/electric-basics-ev"),
                       afdc("vehicles/how-do-plug-in-hybrid-electric-cars-work"), source="afdc"),
                stitch("Benefits, emissions and availability", afdc("fuels/electricity-benefits"), afdc("vehicles/electric-emissions"),
                       afdc("vehicles/electric-availability"), source="afdc")),
            mod("Batteries", afdc("vehicles/electric-batteries"), lec(11, "Batteries and power systems", split=split(1800))),
            mod("Charging", stitch("Charging at home and in public", afdc("fuels/electricity-charging-home"), afdc("fuels/electricity-charging-public"), source="afdc"),
                afdc("fuels/electricity-infrastructure-development", split=split(1600))),
            mod("Maintenance and safety", afdc("vehicles/electric-maintenance"),
                html("https://www.osha.gov/control-hazardous-energy", ("article",), source="osha", title="Controlling hazardous energy (lockout/tagout)")),
        ],
    },
    "precision_agri": {
        "title": "Digital Agriculture with IoT", "subtitle": "Use sensors, automation and cloud services to grow plants with less water and effort.",
        "level": "Beginner", "source": "ms-iot",
        "outcomes": ["Predict plant growth from temperature data", "Measure soil moisture with sensors",
                     "Automate plant watering safely", "Move farm data and logic to the cloud and keep it secure"],
        "modules": [
            mod("Sensing the farm", gh(IOT, "2-farm/lessons/1-predict-plant-growth/README.md"), gh(IOT, "2-farm/lessons/2-detect-soil-moisture/README.md")),
            mod("Automation and the cloud", gh(IOT, "2-farm/lessons/3-automated-plant-watering/README.md"),
                gh(IOT, "2-farm/lessons/4-migrate-your-plant-to-the-cloud/README.md"), gh(IOT, "2-farm/lessons/5-migrate-application-to-the-cloud/README.md"),
                gh(IOT, "2-farm/lessons/6-keep-your-plant-secure/README.md")),
            mod("Seeing from space", html("https://www.earthdata.nasa.gov/learn/earth-observation-data-basics", source="nasa", title="Earth observation data basics")),
        ],
    },
    "gis": {
        "title": "GIS & Geospatial Analysis", "subtitle": "Raster and vector data, coordinate systems, remote sensing and making maps.",
        "level": "Beginner", "source": "dc-geo",
        "outcomes": ["Distinguish raster and vector data and their uses", "Work with coordinate reference systems",
                     "Understand satellite remote sensing data", "Build layered maps in QGIS and Python"],
        "modules": [
            mod("Geospatial concepts", *(carp("datacarpentry/organization-geospatial", e) for e in
                                         ["01-intro-raster-data.Rmd", "02-intro-vector-data.Rmd", "03-crs.Rmd", "04-geo-landscape.Rmd"])),
            mod("Remote sensing", html("https://www.earthdata.nasa.gov/learn/earth-observation-data-basics", source="nasa", title="Earth observation data basics"),
                html("https://www.earthdata.nasa.gov/learn/earth-observation-data-basics/data-processing-levels", source="nasa", title="Data processing levels")),
            mod("Making maps", gh("programminghistorian/jekyll", "en/lessons/qgis-layers.md", "ph", source="ph"),
                gh("programminghistorian/jekyll", "en/lessons/vector-layers-qgis.md", "ph", source="ph"),
                gh("programminghistorian/jekyll", "en/lessons/georeferencing-qgis.md", "ph", source="ph"),
                gh("programminghistorian/jekyll", "en/lessons/choropleth-maps-python-folium.md", "ph", source="ph", split=split(2200))),
        ],
    },
    "circular_economy": {
        "title": "Circular Economy & Waste Management", "subtitle": "Keep materials in use: the waste hierarchy, recycling, composting and your legal duty of care.",
        "level": "Beginner", "source": "epa",
        "outcomes": ["Explain the circular economy and sustainable materials management", "Apply the waste hierarchy",
                     "Run recycling and composting the right way", "Meet the legal duty of care for business waste"],
        "modules": [
            mod("Thinking in circles", html("https://www.epa.gov/circulareconomy/what-circular-economy", ("main article", "article"), title="What is a circular economy?"),
                html("https://www.epa.gov/smm/sustainable-materials-management-basics", ("main article", "article"), title="Sustainable materials management"),
                html("https://www.epa.gov/facts-and-figures-about-materials-waste-and-recycling/national-overview-facts-and-figures-materials",
                     ("main article", "article"), title="Facts and figures on materials and waste", split=split(1800))),
            mod("The waste hierarchy", html("https://environment.ec.europa.eu/topics/waste-and-recycling/waste-framework-directive_en", ("main article", "#main-content"),
                                            source="eu", title="The Waste Framework Directive and the waste hierarchy"),
                govuk("/government/publications/resources-and-waste-strategy-for-england/resources-and-waste-strategy-at-a-glance", source="govuk")),
            mod("Recycling and composting", html("https://www.epa.gov/recycle/recycling-basics-and-benefits", ("main article", "article"), title="Recycling basics and benefits"),
                html("https://www.epa.gov/recycle/composting-home", ("main article", "article"), title="Composting")),
            mod("Business waste duties", govuk("/government/publications/waste-duty-of-care-code-of-practice/waste-duty-of-care-code-of-practice", source="govuk",
                                               title="Waste duty of care", split=split(1800))),
            mod("Circular products", doe("end-life-management-solar-photovoltaics", title="End-of-life management for solar panels")),
        ],
    },
    "electrical": {
        "title": "Electrical & Electronics Fundamentals", "subtitle": "Voltage, current, resistance and power; Ohm's and Kirchhoff's laws; and working safely with electricity.",
        "level": "Beginner", "source": "lec",
        "outcomes": ["Explain charge, voltage, current and resistance", "Calculate circuits with Ohm's law and power formulas",
                     "Analyse series, parallel and divider circuits with Kirchhoff's laws", "Work safely around electrical hazards"],
        "modules": [
            mod("Basic concepts", lec(1, "Basic concepts of electricity", split=split(1800))),
            mod("Ohm's law and power", lec(2, "Ohm's law", split=split(1800))),
            mod("Electrical safety", lec(3, "Electrical safety", split=split(1800)),
                html("https://www.osha.gov/control-hazardous-energy", ("article",), source="osha", title="Controlling hazardous energy (lockout/tagout)")),
            mod("Circuits", lec(5, "Series and parallel circuits", split=split(1800)), lec(6, "Divider circuits and Kirchhoff's laws", split=split(1800))),
        ],
    },
    # ================================================================== Human & Business
    "communication": {
        "title": "Professional Communication", "subtitle": "Write plainly, communicate with stakeholders and share findings people act on.",
        "level": "Beginner", "source": "digitalgov",
        "outcomes": ["Write in plain language for any audience", "Plan communication with stakeholders",
                     "Write effective emails, messages and letters", "Give feedback and present findings clearly"],
        "modules": [
            mod("Plain language",
                stitch("Principles of plain language", html("https://digital.gov/guides/plain-language/principles/", title="Principles of plain language"),
                       html("https://digital.gov/guides/plain-language/writing/", title="Writing for understanding"), source="digitalgov"),
                stitch("Designing and testing for understanding", html("https://digital.gov/guides/plain-language/design/", title="Design for understanding"),
                       html("https://digital.gov/guides/plain-language/test/", title="Test for understanding"), source="digitalgov")),
            mod("Writing at work", sm("design/sending-emails-and-text-messages"), sm("design/writing-effective-letters")),
            mod("Stakeholders", pb(PM, "chapter-5-project-stakeholders-project-management", source="bc-pm", split=split(1600)),
                pb(PM, "chapter-15-communications-planning-project-management", source="bc-pm")),
            mod("Conversations and feedback", pb(TOUR, "communication-strategies", source="tour"),
                pb(L2L, "give-and-receive-feedback", source="l2l"), sm("user-research/sharing-user-research-findings")),
        ],
    },
    "customer_service": {
        "title": "Customer Service & CX", "subtitle": "Deliver remarkable service, build loyalty and design support that works for every customer.",
        "level": "Beginner", "source": "tour",
        "outcomes": ["Explain the customer experience and what customers expect", "Communicate with customers and handle complaints",
                     "Build loyalty and long-term relationships", "Design accessible support across channels and measure satisfaction"],
        "modules": [
            mod("The customer experience", pb(TOUR, "customer-experience"), pb(TOUR, "differences-between-goods-and-services"),
                pb(TOUR, "consumer-behaviour-in-tourism-and-hospitality")),
            mod("Service in action", pb(TOUR, "communication-strategies"), pb(TOUR, "exceeding-expectations"), pb(TOUR, "loyalty-and-customer-relationships")),
            mod("Support for every customer", sm("helping-people-to-use-your-service/set-up-and-manage-user-support"),
                sm("helping-people-to-use-your-service/assisted-digital-support-introduction"),
                sm("user-research/understanding-users-who-dont-use-digital-services"),
                sm("service-standard/point-3-join-up-across-channels")),
            mod("Measuring service", sm("measuring-success/measuring-user-satisfaction"), sm("measuring-success/measuring-the-success-of-your-service")),
        ],
    },
    "project_mgmt": {
        "title": "Project & Agile Delivery Management", "subtitle": "Initiate, plan, run and close projects — with classic project management and agile delivery.",
        "level": "Beginner", "source": "bc-pm",
        "outcomes": ["Explain the project life cycle and the project manager's role", "Plan scope, schedule, budget and risk",
                     "Run agile delivery with Scrum, user stories and roadmaps", "Report progress and close a project well"],
        "modules": [
            mod("Projects and project managers", pb(PM, "chapter-2-what-is-a-project-project-management", split=split(1800)),
                pb(PM, "chapter-3-the-project-life-cycle-phases-project-management"), pb(PM, "chapter-7-project-initiation-project-management", split=split(1800))),
            mod("Planning", pb(PM, "chapter-9-scope-planning-project-management", split=split(1800)),
                pb(PM, "chapter-10-project-schedule-planning-project-management", split=split(1800)),
                pb(PM, "chapter-12-budget-planning-project-management", split=split(1800)),
                pb(PM, "chapter-16-risk-management-planning-project-management", split=split(1800))),
            mod("Agile delivery", sm("agile-delivery/agile-methodologies"), sm("agile-delivery/core-principles-agile"),
                html("https://scrumguides.org/scrum-guide.html", ("#content", "main", "body"), source="scrum", title="The Scrum Guide", split=split(2000)),
                sm("agile-delivery/writing-user-stories"), sm("agile-delivery/deciding-on-priorities"), sm("agile-delivery/developing-a-roadmap")),
            mod("Running and closing", sm("agile-delivery/measuring-reporting-progress"), pb(PM, "chapter-18-project-completion-project-management")),
        ],
    },
    "leadership": {
        "title": "Leadership & People Development", "subtitle": "Lead, organise and motivate people — and build teams that perform.",
        "level": "Beginner", "source": "ostx-biz",
        "outcomes": ["Describe the functions and roles of a manager", "Compare leadership styles and when to use them",
                     "Apply classic and contemporary theories of motivation", "Develop people through high-performance HR practices"],
        "modules": [
            mod("What managers do", stitch("The role of management", biz("6-1-the-role-of-management"), biz("6-3-organizing"), biz("6-5-controlling"), source="ostx-biz"),
                biz("6-2-planning"), stitch("Managerial roles and skills", biz("6-6-managerial-roles"), biz("6-7-managerial-skills"), source="ostx-biz")),
            mod("Leading people", biz("6-4-leading-guiding-and-motivating-others"), biz("6-8-trends-in-management-and-leadership")),
            mod("Motivation", stitch("Early theories of motivation", biz("9-1-early-theories-of-motivation"), biz("9-2-the-hawthorne-studies"), source="ostx-biz"),
                stitch("Maslow, McGregor and Herzberg", biz("9-3-maslows-hierarchy-of-needs"), biz("9-4-mcgregors-theories-x-and-y"),
                       biz("9-5-herzbergs-motivator-hygiene-theory"), source="ostx-biz"),
                biz("9-6-contemporary-views-on-motivation"), biz("9-7-from-motivation-theory-to-application"), biz("9-8-trends-in-employee-motivation")),
            mod("Developing people and teams", biz("8-1-achieving-high-performance-through-human-resources-management"),
                stitch("Effective teamwork", pb(L2L, "understand-the-principles-of-effective-teamwork"), pb(L2L, "plan-for-successful-teamwork"),
                       pb(L2L, "make-commitments-that-support-teamwork"), source="l2l"),
                sm("the-team/set-up-a-service-team")),
        ],
    },
    "analytical_thinking": {
        "title": "Analytical & Critical Thinking", "subtitle": "Question claims, weigh evidence, build sound arguments and reason your way to good decisions.",
        "level": "Beginner", "source": "mt",
        "outcomes": ["Explain what critical thinking is and why it matters", "Follow the stages and dispositions of critical thinking",
                     "Construct and appraise arguments", "Reason deductively and inductively and avoid common fallacies"],
        "modules": [
            mod("What critical thinking is", pb(MT, "chapter-1-what-is-critical-thinking", split=split(1800))),
            mod("Thinking in depth", pb(MT, "chapter-2-critical-thinking-in-depth-stages-steps-and-dispos", split=split(1800))),
            mod("Arguments", pb(MT, "chapter-6-constructing-and-appraising-arguments-part-a", split=split(1800)),
                pb(MT, "chapter-6-part-b-constructing-and-appraising-arguments-edite", split=split(1800))),
            mod("Reasoning", pb(MT, "chapter-7-reasoning-critically-2", split=split(1800))),
            mod("Tools for analysis", gh("18F/methods", "_methods/five-whys.md", source="18f", title="Five whys: finding root causes"),
                pb(BLUEPRINT, "21-words-of-wisdom-thinking-critically-and-creatively", source="blueprint")),
        ],
    },
    "creative_thinking": {
        "title": "Creative & Design Thinking", "subtitle": "Frame problems around people, generate ideas, prototype quickly and learn from testing.",
        "level": "Beginner", "source": "digitalgov",
        "outcomes": ["Explain the human-centred design process", "Frame problems and research them in discovery",
                     "Generate and develop concepts", "Prototype and test ideas to learn fast"],
        "modules": [
            mod("Human-centred design", stitch("Introduction to human-centred design", html("https://digital.gov/guides/hcd/introduction/", title="Introduction"),
                                               html("https://digital.gov/guides/hcd/discovery-concepts/", title="Discovery concepts"), source="digitalgov"),
                html("https://digital.gov/guides/hcd/discovery-operations/", title="Running a discovery"),
                html("https://digital.gov/guides/hcd/design-concepts/", title="Design concepts"),
                html("https://digital.gov/guides/hcd/design-operations/", title="Running design work")),
            mod("The design process", stitch("Define and research", pb(GD, "2-1-introduction"), pb(GD, "4-2-step-1-define"), pb(GD, "2-4-research"), source="bc-gd"),
                pb(GD, "2-5-concept-development", source="bc-gd"), pb(GD, "2-6-solution-implementation", source="bc-gd")),
            mod("Generating ideas", gh("18F/methods", "_methods/design-studio.md", source="18f", title="Design studio"),
                sm("design/map-a-users-whole-problem"), pb(BLUEPRINT, "21-words-of-wisdom-thinking-critically-and-creatively", source="blueprint")),
            mod("Prototyping and testing", sm("design/making-prototypes"),
                stitch("Prototypes and design hypotheses", gh("18F/methods", "_methods/prototyping.md"), gh("18F/methods", "_methods/design-hypothesis.md"),
                       gh("18F/methods", "_methods/storyboarding.md"), source="18f")),
        ],
    },
    "teaching_training": {
        "title": "Teaching & Training Design", "subtitle": "Evidence-based teaching: how people learn, building skill with practice and feedback, and running inclusive sessions.",
        "level": "Beginner", "source": "ci-instructor",
        "outcomes": ["Explain how learners move from novice to expert", "Design lessons that respect memory and cognitive load",
                     "Use formative assessment and feedback", "Create motivating, inclusive and well-managed learning environments"],
        "modules": [
            mod("How learning works", *(carp("carpentries/instructor-training", e) for e in ["02-practice-learning.md", "04-expertise.md", "05-memory.md"])),
            mod("Practice and feedback", *(carp("carpentries/instructor-training", e) for e in ["06-feedback.md", "11-practice-teaching.md", "17-live.md"])),
            mod("Motivation and inclusion", *(carp("carpentries/instructor-training", e) for e in ["08-motivation.md", "09-eia.md", "21-management.md"])),
            mod("Preparing to teach", *(carp("carpentries/instructor-training", e) for e in ["18-preparation.md", "20-performance.md", "24-practices.md"])),
        ],
    },
    "bookkeeping": {
        "title": "Bookkeeping & Accounting Basics", "subtitle": "Record transactions with double-entry bookkeeping, close the books and keep the records the tax office expects.",
        "level": "Beginner", "source": "lumen-fa",
        "outcomes": ["Use the accounting equation and accrual accounting", "Record transactions with debits, credits, journals and ledgers",
                     "Prepare adjusting entries, trial balances and financial statements", "Keep business records that meet tax requirements"],
        "modules": [
            mod("Accounting foundations", stitch("The accounting equation", pb(LFA, "the-accounting-equation"), pb(LFA, "transactions-and-the-accounting-equation")),
                pb(LFA, "financial-statements-2", title="Financial statements"),
                stitch("Accrual and cash basis accounting", pb(LFA, "the-accrual-basis-and-cash-basis-of-accounting"), pb(LFA, "foundational-rules-of-accrual-basis-accounting"))),
            mod("Recording transactions", stitch("Double-entry bookkeeping, accounts, debits and credits", pb(LFA, "introduction-to-double-entry-bookkeeping"),
                                                 pb(LFA, "accounts"), pb(LFA, "rules-of-debits-and-credits")),
                stitch("Journals and ledgers", pb(LFA, "journals"), pb(LFA, "ledgers")),
                stitch("Journalising and posting", pb(LFA, "create-journal-entries"), pb(LFA, "post-to-the-ledger"), pb(LFA, "calculate-account-balances")),
                pb(LFA, "prepare-a-trial-balance", title="Preparing a trial balance")),
            mod("Completing the accounting cycle", stitch("Adjusting entries", pb(LFA, "adjusting-journal-entries"), pb(LFA, "types-of-adjusting-journal-entries")),
                stitch("Deferrals and accruals", pb(LFA, "adjusting-deferred-and-accrued-revenue"), pb(LFA, "adjusting-deferred-and-accrued-expense-items")),
                stitch("Errors and the adjusted trial balance", pb(LFA, "adjusting-for-errors"), pb(LFA, "posting-adjusted-journal-entries-to-the-ledger")),
                stitch("Preparing the financial statements", pb(LFA, "income-statement"), pb(LFA, "balance-sheet"), pb(LFA, "statement-of-cash-flows")),
                stitch("Closing the books", pb(LFA, "introduction-to-closing-the-books"), pb(LFA, "closing-entries"), pb(LFA, "post-closing-trial-balance"))),
            mod("Cash and payroll", stitch("Petty cash and bank reconciliation", pb(LFA, "journalizing-petty-cash-transactions"), pb(LFA, "reconciling-journal-entries")),
                stitch("Payroll", pb(LFA, "payroll-transactions"), pb(LFA, "payroll-journal-entries"))),
            mod("Records the tax office expects", html("https://www.irs.gov/publications/p583", ("main article", "article"), source="irs",
                                                       title="Starting a business and keeping records (IRS Publication 583)", split=split(2200))),
        ],
    },
    "data_entry": {
        "title": "Data Quality for Data Entry", "subtitle": "Collect, enter and organise data so it is accurate, consistent and ready for analysis.",
        "level": "Beginner", "source": "dc-sheets",
        "outcomes": ["Structure data tables so computers can use them", "Avoid the most common spreadsheet mistakes",
                     "Handle dates and validation safely", "Design forms and questions that collect good data"],
        "modules": [
            mod("Good data from the start", *(carp("datacarpentry/spreadsheets-socialsci", e) for e in
                                              ["00-intro.md", "01-format-data.md", "02-common-mistakes.md", "03-dates-as-data.md",
                                               "04-quality-assurance.md", "05-exporting-data.md"])),
            mod("Collecting good data", sm("design/designing-good-questions"), sm("design/form-structure"), sm("design/collecting-personal-information-from-users")),
            mod("Cleaning data", carp("datacarpentry/openrefine-socialsci", "02-working-with-openrefine.md", source="dc-openrefine")),
        ],
    },
    "graphic_design": {
        "title": "Graphic Design & Visual Production", "subtitle": "Design elements and principles, the design process, colour, prepress and print production.",
        "level": "Beginner", "source": "bc-gd",
        "outcomes": ["Apply visual elements and compositional principles", "Follow a professional design process from brief to solution",
                     "Manage colour across screens and print", "Prepare files for production with prepress best practice"],
        "modules": [
            mod("Design foundations", pb(GD, "chapter-1", title="Design history: an introduction"),
                pb(GD, "3-2-visual-elements-basic-things-that-can-be-seen", split=split(2000)),
                pb(GD, "3-3-compositional-principles-strategies-for-arranging-things", split=split(2000)), pb(GD, "3-3-organizational-principles")),
            mod("The design process", stitch("Define and research", pb(GD, "2-1-introduction"), pb(GD, "4-2-step-1-define"), pb(GD, "2-4-research")),
                pb(GD, "2-5-concept-development"), pb(GD, "2-6-solution-implementation")),
            mod("Colour", pb(GD, "colour-science"), pb(GD, "4-4-lab-colour-space-and-delta-e-measurements"),
                pb(GD, "4-10-the-components-and-purpose-of-a-colour-management-syste")),
            mod("Prepress and production", pb(GD, "5-2-raster-image-processing", split=split(2000)), pb(GD, "5-3-colour"), pb(GD, "5-4-trapping"),
                stitch("Transparency, imposition and preflight", pb(GD, "5-5-transparency"), pb(GD, "5-6-imposition"), pb(GD, "5-7-preflight")),
                pb(GD, "6-5-paper-basics")),
        ],
    },
    "healthcare_basics": {
        "title": "Healthcare Domain Essentials", "subtitle": "Medical terminology, the body systems and the health information technology behind modern care.",
        "level": "Beginner", "source": "medterm",
        "outcomes": ["Break medical terms into prefixes, roots and suffixes", "Use terminology for the major body systems",
                     "Explain electronic health records and health information exchange", "Protect the privacy and security of health information"],
        "modules": [
            mod("The language of medicine", stitch("Word parts and language rules", pb(MEDTERM, "chapter-1", title="Identifying word parts"),
                                                   pb(MEDTERM, "medical-language-rules"), pb(MEDTERM, "play", title="Prefixes"), pb(MEDTERM, "suffix", title="Suffixes")),
                pb(MEDTERM, "overview-of-human-anatomy-and-physiology", split=split(2400))),
            mod("Body systems", pb(MEDTERM, "respiratory-system", split=split(2400, take=[0, 1])), pb(MEDTERM, "lympatic-and-blood-systems", split=split(2400, take=[0, 1])),
                pb(MEDTERM, "digestive-systems", split=split(2400, take=[0, 1]))),
            mod("Health information technology",
                html("https://healthit.gov/health-it-basics/benefits-ehrs/", ("div.entry-content",), source="healthit", title="Electronic health records and their benefits"),
                html("https://healthit.gov/health-it-basics/hie/", ("div.entry-content",), source="healthit", title="Health information exchange"),
                html("https://healthit.gov/health-it-basics/improved-diagnostics-patient-outcomes/", ("div.entry-content",), source="healthit",
                     title="Improved diagnostics and patient outcomes"),
                html("https://healthit.gov/privacy-security/", ("div.entry-content",), source="healthit", title="Privacy and security of health information")),
        ],
    },
    "lifelong_learning": {
        "title": "Learning How to Learn", "subtitle": "Manage your time, study effectively, remember more and keep growing through your career.",
        "level": "Beginner", "source": "blueprint",
        "outcomes": ["Plan and monitor your own learning", "Manage time and beat procrastination",
                     "Use proven study, reading and memory techniques", "Build professional skills for lifelong career development"],
        "modules": [
            mod("Self-directed learning", stitch("Becoming a self-directed learner", pb(L2L, "identify-characteristics-of-a-self-directed-learner"),
                                                 pb(L2L, "apply-the-plan-monitor-evaluate-model-for-assessing-your-lea"),
                                                 pb(L2L, "use-critical-questioning-and-reflection-to-support-your-lear"), source="l2l"),
                pb(BLUEPRINT, "17-world-view-and-self-efficacy")),
            mod("Time and focus", pb(BLUEPRINT, "14-time-management-theory", split=split(2000)), pb(BLUEPRINT, "16-time-management-reality"),
                pb(BLUEPRINT, "18-procrastination"), pb(BLUEPRINT, "29-concentration-and-distraction")),
            mod("Studying smarter", pb(BLUEPRINT, "20-the-basics-of-study-skills"), pb(BLUEPRINT, "28-memory"),
                stitch("Strategic reading and note-taking", pb(L2L, "take-effective-notes-on-online-readings"), pb(L2L, "apply-the-sq3r-method"), source="l2l")),
            mod("Growing through your career", pb(BLUEPRINT, "37-professional-skill-building"), pb(BLUEPRINT, "38-career-development"),
                pb(BLUEPRINT, "40-networking")),
        ],
    },
    "finance_domain": {
        "title": "Finance & Financial Analysis", "subtitle": "Read financial statements, analyse performance, manage funds and plan budgets.",
        "level": "Intermediate", "source": "ostx-biz",
        "outcomes": ["Read the balance sheet, income statement and cash flow statement", "Analyse financial statements with ratios",
                     "Explain how organisations obtain and use funds", "Plan budgets and analyse costs"],
        "modules": [
            mod("Financial statements", biz("14-1-accounting-more-than-numbers"), biz("14-3-basic-accounting-procedures"), biz("14-4-the-balance-sheet"),
                stitch("Income and cash flow statements", biz("14-5-the-income-statement"), biz("14-6-the-statement-of-cash-flows"), source="ostx-biz"),
                biz("14-7-analyzing-financial-statements")),
            mod("Financial analysis in depth", pb(FINSTRAT, "the-basic-financial-statements", source="finstrat", split=split(2200))),
            mod("Managing money", biz("16-1-the-role-of-finance-and-the-financial-manager"), biz("16-2-how-organizations-use-funds"),
                stitch("Short- and long-term financing", biz("16-3-obtaining-short-term-financing"), biz("16-4-raising-long-term-financing"), source="ostx-biz"),
                stitch("Equity and securities markets", biz("16-5-equity-financing"), biz("16-6-securities-markets"), source="ostx-biz")),
            mod("Budgets and costs", pb(FINSTRAT, "budgeting", source="finstrat", split=split(2200)),
                pb(FINSTRAT, "cost-analysis", source="finstrat", split=split(2200, take=[0, 1, 2]))),
        ],
    },
}
