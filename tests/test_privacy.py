from lessonweaver.privacy import SimpleRedactor


def test_redacts_email_addresses() -> None:
    assert SimpleRedactor().redact("Email admin@example.com") == "Email [REDACTED]"


def test_redacts_bearer_tokens() -> None:
    token = "Bearer abcdefghijklmnopqrstuvwxyz123456"
    assert SimpleRedactor().redact(f"Auth {token}") == "Auth [REDACTED]"


def test_redacts_api_keys() -> None:
    assert SimpleRedactor().redact("api_key: sk-abc123") == "[REDACTED]"


def test_redacts_aws_access_key() -> None:
    assert SimpleRedactor().redact("AKIAABCDEFGHIJKLMNOP") == "[REDACTED]"


def test_redacts_private_key_header() -> None:
    assert SimpleRedactor().redact("-----BEGIN RSA PRIVATE KEY-----") == "[REDACTED]"


def test_redactor_leaves_plain_text_unchanged() -> None:
    text = "No sensitive pattern here."
    assert SimpleRedactor().redact(text) == text
