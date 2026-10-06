"""Reject incomplete CI parameters and obvious same-machine load/deploy targets."""

from __future__ import annotations

import os
import re
import socket


def main() -> None:
    for name in ("DEPLOY_HOST", "DEPLOY_USER", "DEPLOY_PATH", "IMAGE_REPOSITORY", "REGISTRY"):
        if not os.environ.get(name):
            raise ValueError(f"Configure Jenkins parameter {name}")
    host = os.environ["DEPLOY_HOST"]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*", host):
        raise ValueError("DEPLOY_HOST must be a DNS name or IPv4 address")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]*", os.environ["DEPLOY_USER"]):
        raise ValueError("DEPLOY_USER contains unsupported characters")
    path = os.environ["DEPLOY_PATH"]
    if not re.fullmatch(r"/[a-zA-Z0-9_./-]+", path) or ".." in path.split("/") or path == "/":
        raise ValueError("DEPLOY_PATH must be an absolute directory below /")
    if not re.fullmatch(r"[a-z0-9][a-z0-9./:_-]+", os.environ["IMAGE_REPOSITORY"]):
        raise ValueError("IMAGE_REPOSITORY must be a lowercase registry repository")
    if "your-account" in os.environ["IMAGE_REPOSITORY"]:
        raise ValueError(
            "Replace the IMAGE_REPOSITORY placeholder with your own registry namespace"
        )
    if not re.fullmatch(r"[a-z0-9][a-z0-9.:-]*", os.environ["REGISTRY"]):
        raise ValueError("REGISTRY must be a registry hostname")
    for name in ("PROD_PORT", "LOAD_PORT"):
        port = int(os.environ[name])
        if not 1 <= port <= 65535:
            raise ValueError(f"Invalid {name}")
    if os.environ["PROD_PORT"] == os.environ["LOAD_PORT"]:
        raise ValueError("Production and isolated load services need different ports")
    for name in (
        "P95_THRESHOLD_MS",
        "LOAD_THREADS",
        "LOAD_STEPS",
        "LOAD_RAMP_SECONDS",
        "LOAD_HOLD_SECONDS",
    ):
        if int(os.environ[name]) <= 0:
            raise ValueError(f"{name} must be a positive integer")
    local_names = {"localhost", socket.gethostname().lower(), socket.getfqdn().lower()}
    local_addresses = {"127.0.0.1", "::1", "0.0.0.0"}
    for name in local_names:
        try:
            local_addresses.update(result[4][0] for result in socket.getaddrinfo(name, None))
        except socket.gaierror:
            pass
    addresses = {result[4][0] for result in socket.getaddrinfo(host, None)}
    if host.lower() in local_names or addresses & local_addresses:
        raise ValueError("Deployment/load host must be a different machine from this CI agent")
    print("CI configuration accepted: separate deployment/load target, distinct service ports.")


if __name__ == "__main__":
    main()
