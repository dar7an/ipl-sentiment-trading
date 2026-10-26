"""Check the CA trust boundary without contacting a live API."""

import ssl

import certifi


def test_certifi_does_not_trust_compromised_emsign_root():
    context = ssl.create_default_context(cafile=certifi.where())
    common_names = {
        value
        for certificate in context.get_ca_certs()
        for attributes in certificate["subject"]
        for name, value in attributes
        if name == "commonName"
    }
    assert common_names
    assert "emSign ECC Root CA - G3" not in common_names
