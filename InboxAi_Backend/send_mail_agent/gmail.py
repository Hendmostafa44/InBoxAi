import base64
from email.message import EmailMessage
from email.utils import formataddr
from typing import Sequence

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import text


def get_gmail_account(engine, user_id: int):
    with engine.connect() as connection:
        return connection.execute(
            text("""
                SELECT id, gmail_email, access_token, refresh_token, token_expiry
                FROM gmail_accounts
                WHERE user_id = :user_id
            """),
            {"user_id": user_id},
        ).fetchone()


def _parse_expiry(value):
    if not value:
        return None

    from datetime import datetime

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _save_credentials(engine, account_id: int, credentials: Credentials) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE gmail_accounts
                SET access_token = :access_token,
                    refresh_token = COALESCE(:refresh_token, refresh_token),
                    token_expiry = :token_expiry
                WHERE id = :account_id
            """),
            {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_expiry": credentials.expiry,
                "account_id": account_id,
            },
        )


def send_email(
    engine,
    user_id: int,
    draft: dict[str, str],
    client_id: str,
    client_secret: str,
    scopes: Sequence[str],
) -> None:
    account = get_gmail_account(engine, user_id)
    if not account:
        raise RuntimeError("No Gmail account is connected. Connect Gmail and try again.")

    account_id, sender_email, access_token, refresh_token, token_expiry = account
    if not access_token:
        raise RuntimeError("Your Gmail credentials are missing. Please reconnect Gmail.")
    if not client_id or not client_secret:
        raise RuntimeError("Gmail configuration is incomplete. Please contact the administrator.")

    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        expiry=_parse_expiry(token_expiry),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(scopes),
    )

    try:
        if credentials.expired:
            if not credentials.refresh_token:
                raise RuntimeError("Your Gmail session expired. Please reconnect Gmail.")
            credentials.refresh(GoogleRequest())
            _save_credentials(engine, account_id, credentials)
    except RefreshError as error:
        raise RuntimeError("Gmail authorization could not be refreshed. Please reconnect Gmail.") from error

    message = EmailMessage()
    message["To"] = draft["recipient"]
    message["From"] = formataddr((draft.get("sender_name", ""), sender_email))
    message["Subject"] = draft["subject"]
    message.set_content(draft["body"])

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    try:
        gmail_service = build("gmail", "v1", credentials=credentials)
        gmail_service.users().messages().send(
            userId="me",
            body={"raw": encoded_message},
        ).execute()
    except HttpError as error:
        raise RuntimeError("Gmail could not send the email. Please try again.") from error
    except Exception as error:
        raise RuntimeError("Gmail could not send the email. Please try again.") from error