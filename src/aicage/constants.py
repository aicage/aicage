# ### START: FORK IMAGES ###

# For images built by forks, edit these constants below as needed

IMAGE_REPOSITORY: str = "aicage/aicage"
IMAGE_BASE_REPOSITORY: str = "aicage/aicage-image-base"
IMAGE_UTIL_REPOSITORY: str = "aicage/aicage-image-util"

IMAGE_SOURCE_URL: str = "https://github.com/aicage/aicage-image"
IMAGE_BASE_SOURCE_URL: str = "https://github.com/aicage/aicage-image-base"
IMAGE_UTIL_SOURCE_URL: str = "https://github.com/aicage/aicage-image-util"

VERSION_CHECK_IMAGE: str = "ghcr.io/aicage/aicage-image-util:agent-version"
CREDENTIAL_AGENT_IMAGE: str = "ghcr.io/aicage/aicage-image-util:credential-agent"

# ### END: FORK IMAGES ###

LOCAL_IMAGE_BASE_REPOSITORY: str = "aicage-image-base"
LOCAL_IMAGE_REPOSITORY: str = "aicage"

DEFAULT_IMAGE_BASE: str = "ubuntu"
DEFAULT_EXTENDED_IMAGE_NAME: str = "aicage-extended"

IMAGE_REGISTRY: str = "ghcr.io"
_IMAGE_REGISTRY_API_URL: str = "https://ghcr.io/v2"
_IMAGE_REGISTRY_API_TOKEN_URL: str = (
    "https://ghcr.io/token?service=ghcr.io&scope=repository"
)

_COSIGN_IMAGE_NAME: str = "ghcr.io/sigstore/cosign/cosign"
# _COSIGN_IMAGE_DIGEST holds the digest of
# ghcr.io/sigstore/cosign/cosign:latest
# at the time of a release
_COSIGN_IMAGE_DIGEST: str = (
    "sha256:0f06154836d2de34f887a5c273506d52ca43edaa1d9e53e6510fa78a48f69c2d"
)
COSIGN_IMAGE_REF: str = f"{_COSIGN_IMAGE_NAME}@{_COSIGN_IMAGE_DIGEST}"
COSIGN_OIDC_ISSUER: str = "https://token.actions.githubusercontent.com"
COSIGN_IDENTITY_REGEXP_TEMPLATE: str = (
    r"^https://github.com/{owner}/[^/]+/.github/workflows/.*@(?:refs/.*/.*|[0-9a-f]{{40}})$"
)

DOCKER_LOCAL_METADATA_TIMEOUT_SECONDS: int = 30
DOCKER_PULL_REQUEST_TIMEOUT_SECONDS: int = 60 * 60 * 6
DOCKER_REGISTRY_REQUEST_TIMEOUT_SECONDS: float = 5.0
REGISTRY_DIGEST_REQUEST_TIMEOUT_SECONDS: float = 4.0
PYPI_VERSION_CHECK_TIMEOUT_SECONDS: float = 3.5
PROJECT_FILE_LOCK_TIMEOUT_SECONDS: int = 30
HOST_VERSION_CHECK_TIMEOUT_SECONDS: float = 15.0
BUILDER_VERSION_CHECK_TIMEOUT_SECONDS: float = 20.0
PROXY_ENV_NAMES: tuple[str, ...] = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
)
