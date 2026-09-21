#!/usr/bin/env bash
set -euo pipefail

COSIGN_IMAGE="ghcr.io/sigstore/cosign/cosign:latest"

digest="$(
  cosign verify \
    --output json \
    --certificate-identity keyless@projectsigstore.iam.gserviceaccount.com \
    --certificate-oidc-issuer https://accounts.google.com \
    "${COSIGN_IMAGE}" |
    jq -er '.[0].critical.image["docker-manifest-digest"]'
)"

if [[ ! "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "Could not extract a Cosign image digest from the verification result." >&2
  exit 1
fi

# /_COSIGN_IMAGE_DIGEST: str = \(/        <- ADDRESS: only act on lines matching this
# {                                       <- start a command block for that address
#     N;                                  <- pull in the next line too
#     s#"sha256:[0-9a-f]+"#"${digest}"#   <- the s### command
# }                                       <- end block
sed -i -E \
  -e "/_COSIGN_IMAGE_DIGEST: str = \(/{N; s#\"sha256:[0-9a-f]+\"#\"${digest}\"#}" \
  src/aicage/constants.py
