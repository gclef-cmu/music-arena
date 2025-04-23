import json
import base64
import time
from pathlib import Path
from typing import Optional, Dict, List
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import click
import cryptography

# Store encrypted secrets in the repository directory
REPO_DIR = Path(__file__).parent.parent
SECRETS_FILE = REPO_DIR / "secrets.enc"

# Store encryption key in tmpfs (in-memory filesystem)
# This will be cleared on system reboot
TMPFS_DIR = Path("/dev/shm/secrets")
TMPFS_DIR.mkdir(exist_ok=True, mode=0o700)  # Create with secure permissions
KEY_FILE = TMPFS_DIR / ".key.json"
TTL = 7 * 24 * 60 * 60  # 1 week in seconds

def get_encryption_key(password: str) -> bytes:
    """Derive encryption key from password."""
    salt = b'secrets_salt'  # Fixed salt for consistent key derivation
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def get_cached_key() -> Optional[bytes]:
    """Get cached encryption key if it exists and is not expired."""
    if not KEY_FILE.exists():
        return None
    
    try:
        with open(KEY_FILE, 'r') as f:
            data = json.load(f)
            if time.time() - data['timestamp'] > TTL:
                return None
            return data['key'].encode()
    except (json.JSONDecodeError, KeyError):
        return None

def cache_key(key: bytes):
    """Cache the encryption key with timestamp."""
    with open(KEY_FILE, 'w') as f:
        json.dump({
            'key': key.decode(),
            'timestamp': time.time()
        }, f)

def get_fernet(password: Optional[str] = None) -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    if password is None:
        key = get_cached_key()
        if key is None:
            password = input("Enter encryption password: ")
            key = get_encryption_key(password)
            cache_key(key)
    else:
        key = get_encryption_key(password)
    
    return Fernet(key)

def load_secrets() -> Dict[str, str]:
    """Load encrypted secrets from file."""
    if not SECRETS_FILE.exists():
        return {}
    
    try:
        with open(SECRETS_FILE, 'rb') as f:
            encrypted_data = f.read()
        fernet = get_fernet()
        decrypted_data = fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data)
    except Exception as e:
        if isinstance(e, (cryptography.fernet.InvalidToken, cryptography.fernet.InvalidSignature)):
            click.echo("Error: Invalid password. Please try again.", err=True)
            # Clear the cached key since it's invalid
            if KEY_FILE.exists():
                KEY_FILE.unlink()
            return {}
        click.echo(f"Error loading secrets: {str(e)}", err=True)
        return {}

def save_secrets(secrets: Dict[str, str]):
    """Save secrets to file with encryption."""
    fernet = get_fernet()
    encrypted_data = fernet.encrypt(json.dumps(secrets).encode())
    with open(SECRETS_FILE, 'wb') as f:
        f.write(encrypted_data)

@click.group()
def cli():
    """Manage encrypted secrets."""
    pass

@cli.command()
@click.argument('key')
@click.argument('secret')
def add(key: str, secret: str):
    """Add a new secret."""
    secrets = load_secrets()
    secrets[key] = secret
    save_secrets(secrets)
    click.echo(f"Added secret for {key}")

@cli.command()
@click.argument('key')
def show(key: str):
    """Show a secret."""
    secrets = load_secrets()
    if key not in secrets:
        click.echo(f"No secret found for {key}", err=True)
        return
    click.echo(secrets[key])

@cli.command()
def list():
    """List all secret keys."""
    secrets = load_secrets()
    for key in secrets:
        click.echo(key)

@cli.command()
@click.argument('key')
def delete(key: str):
    """Delete a secret."""
    secrets = load_secrets()
    if key not in secrets:
        click.echo(f"No secret found for {key}", err=True)
        return
    del secrets[key]
    save_secrets(secrets)
    click.echo(f"Deleted secret for {key}")

def get_secret(key: str) -> Optional[str]:
    """Python API to get a secret."""
    secrets = load_secrets()
    return secrets.get(key)

if __name__ == '__main__':
    cli() 