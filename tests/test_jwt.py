#!/usr/bin/env python3
# Usage (from repo root):
#   cd eks && python ../tests/test_jwt.py
#   # or: PYTHONPATH=eks python tests/test_jwt.py
import json, base64, hashlib, time, os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "eks")))
os.environ["NOKE_JWT_SECRET"] = "dISRW8strjOJ0veAj8jg3pgnbmEU3vXmFx4rGx0aloh9eCaYeGzLN09FWwYXX3yjK2kygbUmuAZZTtSrNFIVb62dfwK97K7fe5yI4dGd4YV8dwTvgfKQNULAar8QBHiO"

SECRET = os.environ["NOKE_JWT_SECRET"]

# Header
header = json.dumps({"alg": "NOKE", "typ": "JWT"}, separators=(',', ':'))
header_b64 = base64.urlsafe_b64encode(header.encode()).rstrip(b'=').decode()

# Payload  
exp = int(time.time()) + 31536000
payload = json.dumps({
    "alg": "NOKE",
    "company": "1000233",
    "currentSite": 2223362,
    "deviceId": "",
    "exp": exp,
    "iss": "noke.com",
    "nokeUser": 1034747,
    "sessionSalt": "  ",
    "tokenType": "web"
}, separators=(',', ':'))
payload_b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b'=').decode()

# Signature: SHA256(header + "." + payload + secret) → hex → base64url encode the HEX STRING ITSELF
sig_hex = hashlib.sha256((header_b64 + "." + payload_b64 + SECRET).encode()).hexdigest()
# The hex string itself is what gets base64url-encoded (not the raw bytes)
sig_b64 = base64.urlsafe_b64encode(sig_hex.encode()).rstrip(b'=').decode()

jwt_token = f"{header_b64}.{payload_b64}.{sig_b64}"
print("Generated JWT:")
print(jwt_token)

# Now test if it decodes
from mcp_server.auth.noke_jwt import validate_noke_token
try:
    claims = validate_noke_token(jwt_token)
    print(f"\n✓ JWT valid!")
    print(f"  user_id: {claims['user_id']}")
    print(f"  site_id: {claims['site_id']}")
    print(f"  company: {claims['company']}")
except Exception as e:
    print(f"\n✗ JWT invalid: {type(e).__name__}: {e}")
