# Getting started

1. Install Python 3.10+, create a virtual environment, and install
   `requirements-dev.txt`. Run `python -m pytest -q` offline.
2. Read Reddit's current requirements linked in [the documentation index](README.md).
   Seek approval before accessing the API. Reddit directs developers to Devvit
   first; a local Python implementation is not automatically an exemption.
3. Obtain authorization for this exact use case and permitted communities.
   Third-party AI processing needs explicit authorization; do not hide Gemini
   usage in the application. If it is not permitted, keep drafting disabled.
4. Register the app/developer profile and use the required dedicated app identity.
   Creating script credentials alone does not establish approval.
5. Customize [PRIVACY.md](../PRIVACY.md), set up storage security, and establish a
   deletion contact and a regular cleanup process.
6. Copy `config.example.yaml` to `config.yaml`. Record only real approvals and
   community permissions; see [configuration](configuration.md).
7. Put credentials locally, and set `GEMINI_API_KEY` in your environment only
   if the external-processing workflow is authorized. Do not send credentials
   through chat. Check the configured model exists in your permitted service.
8. Start with `fetch` and `match`, then `draft --limit 1`, `review`, and
   `post --dry-run`. Live `post --limit 1` still requires human confirmation.

No live Reddit/Gemini integration has been verified by this change. Approval is
not guaranteed, and the tool does not independently verify permission records.
