"""Container contracts for the private managed-product volume."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[3]


def test_non_root_api_receives_an_initialised_private_product_volume() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text("utf-8"))
    services = compose["services"]
    initialiser = services["product-storage-init"]
    command = " ".join(initialiser["entrypoint"])

    assert initialiser["user"] == "0:0"
    assert initialiser["network_mode"] == "none"
    assert initialiser["read_only"] is True
    assert initialiser["cap_drop"] == ["ALL"]
    assert initialiser["cap_add"] == ["CHOWN", "DAC_OVERRIDE", "FOWNER"]
    assert "chown -R 10001:10001 /var/lib/mist-products" in command
    assert "product-storage:/var/lib/mist-products" in initialiser["volumes"]
    assert services["api"]["depends_on"]["product-storage-init"] == {
        "condition": "service_completed_successfully"
    }
