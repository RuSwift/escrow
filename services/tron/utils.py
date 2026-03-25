"""
Utility functions for TRON blockchain (address from mnemonic).
По аналогии с https://github.com/RuSwift/garantex/blob/main/services/tron/utils.py
"""
from typing import Tuple

from bip32 import BIP32
from mnemonic import Mnemonic
from tronpy.keys import PrivateKey as TronPrivateKey
from tronpy.keys import is_base58check_address


def is_valid_tron_address(address: str) -> bool:
    """Проверка TRON base58check-адреса (основная сеть)."""
    if not address or not isinstance(address, str):
        return False
    s = address.strip()
    if len(s) != 34:
        return False
    try:
        return bool(is_base58check_address(s))
    except ValueError:
        return False


def address_from_private_key(private_key_hex: str) -> str:
    """TRON address from private key (hex)."""
    priv_key = TronPrivateKey(bytes.fromhex(private_key_hex))
    return priv_key.public_key.to_base58check_address()


def private_key_from_mnemonic(
    mnemonic: str, passphrase: str = "", account_index: int = 0
) -> str:
    """TRON private key from mnemonic (BIP44 path for TRON: m/44'/195'/0'/0/account_index)."""
    mnemo = Mnemonic("english")
    seed = mnemo.to_seed(mnemonic, passphrase)
    bip32_ctx = BIP32.from_seed(seed)
    path = f"m/44'/195'/0'/0/{account_index}"
    derived_key = bip32_ctx.get_privkey_from_path(path)
    return derived_key.hex()


def keypair_from_mnemonic(
    mnemonic: str, passphrase: str = "", account_index: int = 0
) -> Tuple[str, str]:
    """TRON address and private key (hex) from mnemonic. Returns (address, private_key_hex)."""
    private_key = private_key_from_mnemonic(mnemonic, passphrase, account_index)
    address = address_from_private_key(private_key)
    return address, private_key
