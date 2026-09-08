# Security Policy

## Scope

This project publishes study-data tooling and public educational assets. Security reports should focus on repository code, workflows, exposed credentials, privacy leaks, unsafe ingestion behavior, dependency risks, or integrity failures.

## Do not report publicly

If you discover an exposed token, credential, private learner information, or another issue that could be exploited before it is fixed, do not paste the secret or sensitive data into a public issue. Use GitHub's private security-reporting surface when available, or contact the repository owner through a private channel already listed on their GitHub profile.

## Data and privacy rules

- Never commit API keys, cookies, login sessions, MFA material, private Drive links, or learner contact lists.
- Never ingest private learner conversations or personal records into the public commons without explicit lawful authorization and safe de-identification.
- Public contribution workflows must not scrape or mass-message private contacts.
- Any future automation that writes to GitHub, Hugging Face, Drive, or another service must use least-privilege credentials and must be independently verified before being described as live.

## Integrity issues

Please report reproducible cases of duplicate identifiers, broken provenance, incorrect hashes, source/license mismatch, misleading deployment claims, or data/schema drift. Include the affected path, expected behavior, observed behavior, and a minimal reproduction when possible.
