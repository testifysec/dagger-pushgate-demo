#!/usr/bin/env python3
"""Write policy/policy.json: one step, signed by the throwaway E1 key.
usage: build-policy.py <pubkey.pem> <out.json>"""
import base64, hashlib, json, sys
pub = open(sys.argv[1], "rb").read()
# cilock's keyid for a file key: sha256 of the PEM public key (matches the envelope keyid)
keyid = hashlib.sha256(pub).hexdigest()
rego = base64.b64encode(open(__file__.rsplit("/", 1)[0] + "/dagger-evidence.rego", "rb").read()).decode()
pol = {
    "expires": "2027-10-28T00:00:00Z",
    "publickeys": {keyid: {"keyid": keyid, "key": base64.b64encode(pub).decode()}},
    "steps": {"dagger-check": {
        "name": "dagger-check",
        "functionaries": [{"type": "publickey", "publickeyid": keyid}],
        "attestations": [{
            "type": "https://aflock.ai/attestations/command-run/v0.2",
            "regopolicies": [{"name": "dagger-evidence", "module": rego}],
        }],
    }},
}
json.dump(pol, open(sys.argv[2], "w"), indent=2)
print(keyid)
