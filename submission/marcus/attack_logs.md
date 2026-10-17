# Attack Logs – Simulated Attacks

These tests were run against our own deployment on 16 October 2026 to check that the security controls work and that the logs show what happened.

Two accounts were used:
- Alice (user_id=61)
- Bob (user_id=62)

## Setup

Create the users, log in, and upload a document as Alice.

```bash
# Create users
curl -s -X POST http://localhost:5000/api/create-user \
  -H "Content-Type: application/json" \
  -d '{"email":"alice3@example.com","login":"alice3","password":"alice123"}'

curl -s -X POST http://localhost:5000/api/create-user \
  -H "Content-Type: application/json" \
  -d '{"email":"bob3@example.com","login":"bob3","password":"bob123"}'

# Get tokens
TOKEN_A=$(curl -s -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice3@example.com","password":"alice123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

TOKEN_B=$(curl -s -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"bob3@example.com","password":"bob123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Alice uploads a document (note the returned id)
curl -s -X POST http://localhost:5000/api/upload-document \
  -H "Authorization: Bearer $TOKEN_A" \
  -F "file=@/tmp/test.pdf" \
  -F "name=alice-doc.pdf"
```

## 1. IDOR on watermark creation

**Goal:** Check that Bob cannot create a watermark on Alice’s document.

```bash
curl -s -X POST http://localhost:5000/api/create-watermark \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 35,
    "method": "watermark_marcus",
    "intended_for": "bob-attack",
    "secret": "stolen",
    "key": "key"
  }'
```

**Log:**
```
watermark_create_attempt document_id=35 method=watermark_marcus intended_for=bob-attack user_id=62 ip=172.18.0.1
watermark_access_denied document_id=35 user_id=62 ip=172.18.0.1
```

**Result:** Stopped. The ownership check rejected the request.

## 2. Brute-force login

**Goal:** Check that repeated failed logins are limited.

```bash
for i in {1..15}; do
  curl -s -X POST http://localhost:5000/api/login \
    -H "Content-Type: application/json" \
    -d '{"email":"alice3@example.com","password":"wrong"}'
  echo
done
```

**Log:**
```
login_failure reason=invalid_credentials email=alice3@example.com ip=172.18.0.1
... (repeated) ...
rate_limit_exceeded ip=172.18.0.1 path=/api/login
```

**Result:** Stopped after 10 attempts by the rate limiter.

## 3. Open version link

**Goal:** Check whether a version link can be used without login.

```bash
# Alice creates a watermark and receives a link
curl -s -X POST http://localhost:5000/api/create-watermark \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 35,
    "method": "watermark_marcus",
    "intended_for": "version-link-test",
    "secret": "link-secret",
    "key": "key"
  }'

# Download without a token
curl -s -o /tmp/stolen.pdf \
  http://localhost:5000/api/get-version/bc4a589fc8806d5d12a158b4d436308bd02011b1
```

**Log:**
```
watermark_created document_id=35 version_id=79 link=bc4a589fc8806d5d12a158b4d436308bd02011b1 method=watermark_marcus intended_for=version-link-test user_id=61
version_downloaded link=bc4a589fc8806d5d12a158b4d436308bd02011b1 intended_for=version-link-test document_id=35 ip=172.18.0.1
```

**Result:** Succeeded. The link does not require authentication. The download is logged, but not blocked.

## 4. Unauthorized deletion

**Goal:** Check that Bob cannot delete Alice’s document, and that Alice can delete her own.

```bash
# Alice uploads a new document (note the returned id)
curl -s -X POST http://localhost:5000/api/upload-document \
  -H "Authorization: Bearer $TOKEN_A" \
  -F "file=@/tmp/test.pdf" \
  -F "name=alice-doc2.pdf"

# Bob tries to delete it
curl -s -X DELETE http://localhost:5000/api/delete-document/36 \
  -H "Authorization: Bearer $TOKEN_B"

# Alice deletes her own document
curl -s -X DELETE http://localhost:5000/api/delete-document/36 \
  -H "Authorization: Bearer $TOKEN_A"
```

**Log:**
```
document_uploaded document_id=36 name=alice-doc2.pdf user_id=61 ip=172.18.0.1
delete_access_denied document_id=36 user_id=62 ip=172.18.0.1
document_deleted document_id=36 user_id=61 ip=172.18.0.1
```

**Result:** Bob was denied. Alice could delete her own document. Both events are logged.

## 5. External activity (hacker2)

This was not simulated by us. During testing the logs showed activity from another machine on the course network.

**Log:**
```
login_success user_id=54 login=hacker2 email=hacker2@test.com ip=10.100.10.59
auth_success user_id=54 login=hacker2 ip=10.100.10.59 path=/api/list-all-versions
```

**Result:** Detected by logging. The ownership filter on list-all-versions limited what the user could see.
