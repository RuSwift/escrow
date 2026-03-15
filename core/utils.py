"""
Utility functions for working with DIDs and other ledger-related identifiers
"""
import hashlib
from typing import Optional, Tuple
import uuid
import base58
import base64
from io import BytesIO
from PIL import Image


def get_user_did(wallet_address: str, blockchain: str) -> str:
    """
    Формирует DID из wallet_address и blockchain
    
    Args:
        wallet_address: Адрес кошелька пользователя
        blockchain: Тип блокчейна (tron, ethereum, bitcoin, etc.)
    
    Returns:
        DID строка в формате did:{method}:{address}
    """
    blockchain_lower = blockchain.lower()
    
    if blockchain_lower in ['tron', 'ethereum', 'bitcoin']:
        # TRON, Ethereum, Bitcoin use secp256k1. Только Ethereum нормализуем в lower (EIP-55).
        did_method = "ethr" if blockchain_lower == "ethereum" else blockchain_lower
        addr = wallet_address.lower() if blockchain_lower == "ethereum" else wallet_address.strip()
        did = f"did:{did_method}:{addr}"
    elif blockchain_lower in ['polkadot', 'substrate']:
        # Polkadot uses Ed25519
        did = f"did:polkadot:{wallet_address.strip()}"
    else:
        # Default to secp256k1 for unknown blockchains
        did = f"did:ethr:{wallet_address.strip()}"
    
    return did


def get_deal_did(deal_uid: str) -> str:
    return f'did:deal:{deal_uid}'


def get_wallet_did(wallet_id: int, node_did: str) -> str:
    """
    Уникальный DID кошелька с префиксом ноды.
    Формат: did:ruswift:{node_prefix}:wallet:{wallet_id}
    node_prefix берётся из DID ноды (суффикс после did:peer:1: или хеш).
    """
    if not node_did or not node_did.strip():
        node_prefix = "local"
    elif node_did.startswith("did:peer:1:"):
        suffix = node_did[len("did:peer:1:"):].strip()
        node_prefix = suffix if suffix else "local"
    else:
        node_prefix = hashlib.sha256(node_did.encode()).hexdigest()[:16]
    return f"did:{node_prefix}:wallet:{wallet_id}"


def generate_base58_uuid() -> str:
    """
    Generate a base58-encoded UUID v4
    
    Returns:
        Base58-encoded UUID string
    """
    # Generate UUID v4
    uuid_obj = uuid.uuid4()
    
    # Convert to bytes (16 bytes for UUID)
    uuid_bytes = uuid_obj.bytes
    
    # Encode to base58
    base58_encoded = base58.b58encode(uuid_bytes).decode('utf-8')
    
    return base58_encoded


def get_image_dimensions(base64_data: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Get image dimensions from base64 data
    
    Args:
        base64_data: Base64 encoded image data
    
    Returns:
        Tuple of (width, height) or (None, None) if unable to determine
    """
    try:
        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_data)
        
        # Open image with PIL
        image = Image.open(BytesIO(image_bytes))
        
        # Get dimensions
        width, height = image.size
        
        return width, height
    except Exception as e:
        print(f"Error getting image dimensions: {e}")
        return None, None
