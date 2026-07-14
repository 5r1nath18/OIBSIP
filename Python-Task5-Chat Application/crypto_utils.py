
import base64
import hashlib
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken

# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #

PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16


def hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
    """Return (hash_hex, salt_hex) for the given password.

    If salt is not provided, a new random salt is generated (use this
    path when registering a new user). Pass the stored salt back in
    when verifying a login attempt.
    """
    if salt is None:
        salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, stored_hash_hex: str, salt_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    candidate_hash, _ = hash_password(password, salt)
    # Constant-time comparison to avoid timing side-channel attacks
    return hmac.compare_digest(candidate_hash, stored_hash_hex)


# --------------------------------------------------------------------------- #
# Message encryption (Fernet symmetric key)
# --------------------------------------------------------------------------- #

DEFAULT_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secret.key")


def generate_key_file(path: str = DEFAULT_KEY_FILE) -> bytes:
    """Generate a new Fernet key and save it to `path`. Returns the key bytes."""
    key = Fernet.generate_key()
    with open(path, "wb") as f:
        f.write(key)
    return key


def load_key(path: str = DEFAULT_KEY_FILE) -> bytes:
    """Load the shared Fernet key, generating one if it doesn't exist yet."""
    if not os.path.exists(path):
        return generate_key_file(path)
    with open(path, "rb") as f:
        return f.read().strip()


class MessageCipher:
    """Wraps Fernet for encrypting/decrypting chat payloads (text or base64 media)."""

    def __init__(self, key: bytes = None, key_path: str = DEFAULT_KEY_FILE):
        self.key = key or load_key(key_path)
        self._fernet = Fernet(self.key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a UTF-8 string, return a base64 ciphertext string (safe for JSON)."""
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a base64 ciphertext string back to the original UTF-8 string."""
        try:
            plaintext = self._fernet.decrypt(ciphertext.encode("ascii"))
        except InvalidToken as exc:
            raise ValueError("Message could not be decrypted (wrong key or corrupted data).") from exc
        return plaintext.decode("utf-8")


def encode_bytes(data: bytes) -> str:
    """Base64-encode raw bytes (e.g. an image/file) into a string for JSON/encryption."""
    return base64.b64encode(data).decode("ascii")


def decode_bytes(data_str: str) -> bytes:
    """Reverse of encode_bytes."""
    return base64.b64decode(data_str.encode("ascii"))
