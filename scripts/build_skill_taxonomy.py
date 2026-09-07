"""Generates data/taxonomy/skills_taxonomy.json.

Checked into git as a static file so the app never needs to run this at
runtime -- this script exists purely so the taxonomy is maintainable and
reproducible (add/edit an entry here, regenerate) instead of hand-edited
JSON.

This is a curated STARTER taxonomy (~100 entries), not an exhaustive
industry-standard one (e.g. ESCO or O*NET) -- those require network
access to a data source outside this environment's reachable domains,
and a much larger scope than this project's starter taxonomy requires. It is
explicitly not claimed to be complete; see data/taxonomy/README.md.

Each entry: canonical_name (the display form normalization returns),
category (informational, not used for matching), aliases (variant
phrasings that should resolve to this entry). Aliases are genuinely
equivalent phrasings only -- not merely related concepts -- so
normalization never conflates two actually-distinct skills.
"""

from __future__ import annotations

import json
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "taxonomy" / "skills_taxonomy.json"

ENTRIES = [
    # --- Languages ---
    ("Python", "Language", ["Python 3", "Python3", "Py"]),
    ("JavaScript", "Language", ["JS", "Javascript", "ECMAScript"]),
    ("TypeScript", "Language", ["TS"]),
    ("Java", "Language", []),
    ("C++", "Language", ["Cpp", "C plus plus"]),
    ("C#", "Language", ["C Sharp", "CSharp"]),
    ("Go", "Language", ["Golang"]),
    ("Ruby", "Language", []),
    ("PHP", "Language", []),
    ("Swift", "Language", []),
    ("Kotlin", "Language", []),
    ("Scala", "Language", []),
    ("Rust", "Language", []),
    ("R", "Language", ["R Language", "R Programming"]),
    ("MATLAB", "Language", []),
    ("Bash", "Language", ["Shell Scripting", "Shell"]),
    ("PowerShell", "Language", []),
    ("SQL", "Language", ["Structured Query Language"]),
    ("HTML", "Language", ["HTML5"]),
    ("CSS", "Language", ["CSS3"]),
    # --- Frameworks / libraries ---
    ("React", "Framework", ["React.js", "ReactJS", "React JS"]),
    ("Angular", "Framework", ["AngularJS", "Angular JS"]),
    ("Vue.js", "Framework", ["Vue", "VueJS", "Vue JS"]),
    ("Node.js", "Framework", ["NodeJS", "Node JS", "Node"]),
    ("Express.js", "Framework", ["Express", "ExpressJS"]),
    ("Django", "Framework", []),
    ("Flask", "Framework", []),
    ("FastAPI", "Framework", ["Fast API"]),
    ("Spring Boot", "Framework", ["Spring", "SpringBoot"]),
    (".NET", "Framework", ["Dot Net", "DotNet", ".NET Core"]),
    ("Ruby on Rails", "Framework", ["Rails"]),
    ("Next.js", "Framework", ["NextJS", "Next JS"]),
    ("jQuery", "Framework", []),
    ("Bootstrap", "Framework", []),
    ("Tailwind CSS", "Framework", ["TailwindCSS", "Tailwind"]),
    ("Scikit-learn", "Framework", ["sklearn", "Scikit Learn"]),
    ("TensorFlow", "Framework", []),
    ("PyTorch", "Framework", []),
    ("Keras", "Framework", []),
    ("Pandas", "Framework", []),
    ("NumPy", "Framework", []),
    ("LangChain", "Framework", []),
    # --- Databases ---
    ("PostgreSQL", "Database", ["Postgres", "Postgre SQL", "PostgresSQL"]),
    ("MySQL", "Database", ["My SQL"]),
    ("MongoDB", "Database", ["Mongo DB", "Mongo"]),
    ("Redis", "Database", []),
    ("SQLite", "Database", ["SQ Lite"]),
    ("Oracle Database", "Database", ["Oracle DB", "Oracle SQL"]),
    ("Microsoft SQL Server", "Database", ["MSSQL", "SQL Server", "MS SQL"]),
    ("Cassandra", "Database", ["Apache Cassandra"]),
    ("DynamoDB", "Database", ["Dynamo DB"]),
    ("Elasticsearch", "Database", ["Elastic Search"]),
    ("Snowflake", "Database", []),
    # --- Cloud / DevOps ---
    ("AWS", "Cloud/DevOps", ["Amazon Web Services"]),
    ("Azure", "Cloud/DevOps", ["Microsoft Azure"]),
    ("GCP", "Cloud/DevOps", ["Google Cloud Platform", "Google Cloud"]),
    ("Docker", "Cloud/DevOps", []),
    ("Kubernetes", "Cloud/DevOps", ["K8s"]),
    ("Terraform", "Cloud/DevOps", []),
    ("Ansible", "Cloud/DevOps", []),
    ("Jenkins", "Cloud/DevOps", []),
    ("GitHub Actions", "Cloud/DevOps", []),
    ("GitLab CI", "Cloud/DevOps", ["GitLab CI/CD"]),
    ("CircleCI", "Cloud/DevOps", ["Circle CI"]),
    (
        "CI/CD",
        "Cloud/DevOps",
        ["Continuous Integration", "Continuous Deployment", "Continuous Delivery"],
    ),
    ("Git", "Cloud/DevOps", []),
    ("Linux", "Cloud/DevOps", []),
    ("Nginx", "Cloud/DevOps", []),
    ("Chef", "Cloud/DevOps", []),
    ("Puppet", "Cloud/DevOps", []),
    # --- Data / ML / AI ---
    ("Machine Learning", "Data/ML", ["ML"]),
    ("Deep Learning", "Data/ML", ["DL"]),
    ("Artificial Intelligence", "Data/ML", ["AI"]),
    ("Natural Language Processing", "Data/ML", ["NLP"]),
    ("Computer Vision", "Data/ML", ["CV"]),
    ("Data Analysis", "Data/ML", ["Data Analytics"]),
    ("Data Visualization", "Data/ML", []),
    ("Apache Spark", "Data/ML", ["Spark", "PySpark"]),
    ("Apache Kafka", "Data/ML", ["Kafka"]),
    ("Apache Airflow", "Data/ML", ["Airflow"]),
    ("Apache Hadoop", "Data/ML", ["Hadoop"]),
    ("Tableau", "Data/ML", []),
    ("Power BI", "Data/ML", ["PowerBI"]),
    ("Looker", "Data/ML", []),
    # --- Tools / platforms ---
    ("Jira", "Tool", []),
    ("Confluence", "Tool", []),
    ("Figma", "Tool", []),
    ("Adobe Photoshop", "Tool", ["Photoshop"]),
    ("Adobe Illustrator", "Tool", ["Illustrator"]),
    ("Salesforce", "Tool", []),
    ("SAP", "Tool", []),
    ("Microsoft Excel", "Tool", ["Excel"]),
    ("Slack", "Tool", []),
    ("Notion", "Tool", []),
    # --- APIs / architecture ---
    ("REST", "Architecture", ["RESTful", "REST API", "REST APIs"]),
    ("GraphQL", "Architecture", []),
    ("gRPC", "Architecture", []),
    ("Microservices", "Architecture", ["Microservice Architecture"]),
    ("SOAP", "Architecture", []),
    ("WebSockets", "Architecture", ["WebSocket"]),
    # --- Practices / methodologies ---
    ("Agile", "Practice", ["Agile Methodology"]),
    ("Scrum", "Practice", []),
    ("Kanban", "Practice", []),
    ("DevOps", "Practice", []),
    ("Test-Driven Development", "Practice", ["TDD"]),
    ("Object-Oriented Programming", "Practice", ["OOP"]),
    ("Pair Programming", "Practice", []),
    # --- Testing ---
    ("Selenium", "Testing", []),
    ("Pytest", "Testing", ["PyTest"]),
    ("JUnit", "Testing", []),
    ("Cypress", "Testing", []),
]


def main() -> None:
    data = {
        "entries": [
            {"canonical_name": name, "category": category, "aliases": aliases}
            for name, category, aliases in ENTRIES
        ]
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Wrote {len(ENTRIES)} entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

