from __future__ import annotations

import typer

from roambot.config import Settings
from roambot.security.vault import CredentialVault, VaultAuthenticationError

app = typer.Typer(no_args_is_help=True)
credentials_app = typer.Typer(no_args_is_help=True)
app.add_typer(credentials_app, name="credentials")

_SERVICES = {
    "amap": "amap_api_key",
    "qweather": "qweather_api_key",
    "llm": "llm_api_key",
}


def _vault() -> CredentialVault:
    return CredentialVault(Settings().data_dir / "credentials.vault")


def _master_password(*, confirmation: bool = False) -> str:
    return typer.prompt("主密码", hide_input=True, confirmation_prompt=confirmation)


def _authentication_failure() -> None:
    typer.echo("Unable to authenticate credential vault.", err=True)
    raise typer.Exit(code=1)


def _existing_vault() -> CredentialVault:
    vault = _vault()
    if not vault.path.exists():
        typer.echo("Credential vault has not been initialized.", err=True)
        raise typer.Exit(code=1)
    return vault


def _status_line(service: str, configured: bool) -> None:
    typer.echo(f"{service}: {'configured' if configured else 'unconfigured'}")


@credentials_app.command()
def init() -> None:
    vault = _vault()
    if vault.path.exists():
        typer.echo("Credential vault already exists.", err=True)
        raise typer.Exit(code=1)
    vault.create(_master_password(confirmation=True))
    typer.echo("Credential vault initialized.")


@credentials_app.command()
def status() -> None:
    vault = _vault()
    if not vault.path.exists():
        for service in _SERVICES:
            _status_line(service, False)
        return
    try:
        credentials = vault.unlock(_master_password())
    except VaultAuthenticationError:
        _authentication_failure()
    for service, credential_name in _SERVICES.items():
        _status_line(service, credentials[credential_name] is not None)


@credentials_app.command("set")
def set_credential(service: str) -> None:
    credential_name = _SERVICES.get(service)
    if credential_name is None:
        typer.echo("Unsupported credential service.", err=True)
        raise typer.Exit(code=1)
    vault = _existing_vault()
    try:
        vault.update(
            _master_password(),
            credential_name,
            typer.prompt(f"{service} API key", hide_input=True),
        )
    except VaultAuthenticationError:
        _authentication_failure()
    typer.echo(f"{service}: configured")


@credentials_app.command()
def clear(service: str) -> None:
    credential_name = _SERVICES.get(service)
    if credential_name is None:
        typer.echo("Unsupported credential service.", err=True)
        raise typer.Exit(code=1)
    vault = _existing_vault()
    try:
        vault.clear(_master_password(), credential_name)
    except VaultAuthenticationError:
        _authentication_failure()
    typer.echo(f"{service}: unconfigured")


@credentials_app.command()
def reset() -> None:
    confirmation = typer.prompt("Type RESET-CREDENTIALS to confirm")
    if confirmation != "RESET-CREDENTIALS":
        typer.echo("Credential reset cancelled.", err=True)
        raise typer.Exit(code=1)
    vault = _vault()
    try:
        vault.reset()
    except VaultAuthenticationError:
        typer.echo("Unable to reset credential vault.", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Credential vault reset.")
