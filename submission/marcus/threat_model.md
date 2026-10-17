# Threat Model – Tatou

This document describes the main assets, trust boundaries and threats for the Tatou deployment, and the controls that were added.

## Assets

| Asset | Where it lives | Why it matters |
|-------|----------------|----------------|
| Original PDF | File system + Documents table | Only the owner should be able to access it |
| Watermark secret | Versions.secret + embedded in PDF | Reveals who a document was intended for |
| Version link | Versions.link | Allows download of a watermarked PDF without login |
| User credentials | Users table | Used for authentication |
| Session token | Client + itsdangerous | Grants access to the API |
| RMAP keys | File system (env paths) | Used to authenticate other groups |
| Flags | File system / environment | Course targets |

## Trust Boundaries

1. **Network → Application** – External requests enter through the Flask API.
2. **Application → Database** – The API reads and writes user and document data in MariaDB.
3. **Application → File system** – PDFs are stored under STORAGE_DIR.
4. **External group → RMAP** – Other groups authenticate with OpenPGP instead of HTTP tokens.

## STRIDE

### Spoofing
Pretending to be another user.

- **Example:** Brute-force login or reuse of a stolen token.
- **Control:** Tokens are signed. Login is rate-limited.
- **Log:** `login_failure`, `rate_limit_exceeded`
- **Limitation:** Rate limiting is in-memory and resets on restart.

### Elevation of privilege
Doing something you are not allowed to do.

- **Example:** Create or delete a watermark on another user’s document.
- **Control:** Queries check both document id and `ownerid`.
- **Log:** `watermark_access_denied`, `delete_access_denied`

### Tampering / Repudiation
Changing data or denying that you did something.

- **Example:** Delete a document and later claim you did not.
- **Control:** Ownership check plus a log entry on successful deletion.
- **Log:** `document_deleted`

### Information disclosure
Seeing data you should not see.

- **Example:** Download a PDF using a leaked version link.
- **Control:** The link is hard to guess, but it is not authenticated. Logging shows that a download happened; it does not stop it.
- **Log:** `version_downloaded`
- **Residual risk:** Anyone who has the link can download the PDF.

### Denial of Service
Making the service unavailable.

- **Example:** Many login or RMAP requests in a short time.
- **Control:** Simple in-memory rate limiter.
- **Log:** `rate_limit_exceeded`
- **Limitation:** The limiter resets if the container restarts.

## RMAP

RMAP endpoints authenticate the caller with OpenPGP instead of HTTP tokens.  
A suggested library update (v2.0.0 wheel) contained a backdoor that read `/app/flag` and sent it to internal addresses. We kept the official git tag v1.0.2 and did not install the wheel.

## Residual Risks

- Version links do not require login. Knowing the link is enough to download the PDF.
- Rate limiting lives in memory and is lost on restart.
- There is no automated alerting. Detection depends on looking at the container logs.
