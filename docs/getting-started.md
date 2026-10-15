# Getting started

Install Python 3.10+ and the dependencies in requirements-dev.txt. Copy
config.example.yaml to config.yaml. Inject Reddit secrets using environment
variables through your trusted credential manager.

Do not enable live access until Reddit has approved the exact use case.
Assess Devvit first; the local CLI alone does not justify an exception.
Register the app and use a dedicated, appropriately labeled app account.
Complete PRIVACY.md and configure exactly one permitted community.

Select one post ID yourself. Write a human reply in a UTF-8 file, then run:

```powershell
python main.py draft abc123 --text-file my-reply.txt
python main.py review abc123
python main.py post abc123
```

Run python main.py maintenance in a separate terminal for hourly local cleanup.
