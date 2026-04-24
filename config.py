import os
import pathlib


DEFAULT_POWERBI_URL = (
    "https://app.powerbi.com/groups/7ece2d6d-0e30-4470-ae37-f6f1f4a2eb6d/"
    "reports/9eef11ad-17a7-4035-bf27-37c8cb888e88/ReportSection7904145abaf3870d6a0d"
)
DEFAULT_SUPERADMIN_EMAIL = "danielgilabert@prode.es"


def load_runtime_env() -> None:
    try:
        import streamlit as st

        secrets = st.secrets
        for key in (
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "LOG_LEVEL",
            "POWERBI_URL",
            "SUPERADMIN_EMAIL",
        ):
            if key in secrets and key not in os.environ:
                os.environ[key] = str(secrets[key])
    except Exception:
        pass

    base = pathlib.Path(__file__).resolve().parent
    for name in ("key.env", ".env", "1.env", "key.env.txt", "1.env.txt"):
        candidate = base / name
        if candidate.exists():
            with open(candidate, encoding="utf-8-sig") as file:
                for raw_line in file:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
            return


def get_superadmin_email() -> str:
    load_runtime_env()
    return os.environ.get("SUPERADMIN_EMAIL", DEFAULT_SUPERADMIN_EMAIL).strip().lower()


def is_superadmin_email(email: str) -> bool:
    return email.strip().lower() == get_superadmin_email()


def get_powerbi_url() -> str:
    load_runtime_env()
    return os.environ.get("POWERBI_URL", DEFAULT_POWERBI_URL).strip()
