# Aura Claim Loop Toolkit

A Python toolkit for quantifying insurance-claim recursive administration loops.

It converts connected-app timestamps into evidence-ready reports:

- `normalized_claim_events.csv`
- `time_to_ack_report.csv`
- `recursive_loop_report.csv`
- `summary.json`
- `claim_delay_exhibit.md`

## 1. Install

```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows PowerShell

pip install -r requirements.txt
```

## 2. Run the sample

```bash
python claim_loop_analyzer.py --input sample_claim_events.csv --output outputs --ack-hours 168
```

`168` hours equals 7 days. Adjust this to match your state, policy, or claim-handling benchmark.

## 3. Run as an API

```bash
uvicorn aura_api_server:app --reload
```

Then call:

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"input_csv":"sample_claim_events.csv","output_dir":"outputs","ack_hours":168}'
```

## 4. Input schema

Required CSV columns:

```text
claim_id,event_time,event_type,source_app,actor,subject,thread_id,document_type,evidence_url,notes
```

Event types:

```text
claim_submitted
document_uploaded
email_sent
email_received
acknowledgement
duplicate_request
status_change
phone_call
voicemail
escalation
denial
payment
silence_gap
```

## 5. What the program measures

### Time to acknowledgement

```text
time_to_ack = acknowledgement_time - sent_or_uploaded_time
```

### Delay

```text
delay = max(0, time_to_ack - acknowledgement_benchmark)
```

### Recursive loop indicators

The program flags:

- duplicate requests after a prior submission
- silence gaps
- escalations
- open submissions with no acknowledgement

## 6. Connected apps

Use `connected_app_template.py` to map Aura, Gmail, Outlook, claim portals, Drive, OneDrive, or CRM records into the normalized CSV schema.

Do not hard-code secrets. Use OAuth and environment variables.
