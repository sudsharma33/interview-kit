# Sample data

Drop-in inputs for quick demos and manual testing.

| File | Use as |
|---|---|
| `sample_jd.txt` | Job Description input |
| `sample_resume.txt` | Candidate Resume input |

## Why these specifically

The sample pair is deliberately designed to produce a **realistic, mixed result** — not a perfect match, not a total mismatch:

**Matches the candidate should hit**
- Python, Django, FastAPI
- PostgreSQL, SQL
- REST APIs, unit / integration tests
- Git, Docker, CI/CD, Linux
- ~3 years experience (fits the 2–4 range)

**Gaps the candidate has**
- No Go experience
- No Kafka / event streaming
- Only "basic" AWS exposure (JD asks for ECS, RDS, SQS, Lambda)
- No gRPC
- No observability tooling (Datadog / Grafana / Prometheus)
- No payments / fintech background
- No on-call experience mentioned

This mix is what makes the demo compelling — the **gap-probing questions** section actually has something interesting to probe.

## How to use during the demo

1. Open the app
2. In the **Job Description** column, click upload and pick `samples/sample_jd.txt`
3. In the **Candidate Resume** column, upload `samples/sample_resume.txt`
4. Click **Generate Interview Kit**
5. Walk the panel through the matched skills, gap skills, and the gap-probing questions

Total demo time: under 2 minutes.
