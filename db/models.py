"""
Database models for storing encrypted node settings
"""
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Boolean, Index, Numeric, ForeignKey, event, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB, JSON
from sqlalchemy.sql import func
import uuid
from db import Base


class NodeSettings(Base):
    """Model for storing encrypted mnemonic and PEM data"""
    
    __tablename__ = "node_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Encrypted mnemonic phrase (if using mnemonic)
    encrypted_mnemonic = Column(Text, nullable=True, comment="Encrypted mnemonic phrase")
    
    # Encrypted PEM data (if using PEM key)
    encrypted_pem = Column(Text, nullable=True, comment="Encrypted PEM key data")
    
    # Key type: 'mnemonic' or 'pem'
    key_type = Column(String(20), nullable=False, default='mnemonic', comment="Type of key: mnemonic or pem")
    
    # Ethereum address derived from the key
    ethereum_address = Column(String(42), nullable=True, unique=True, index=True, comment="Ethereum address")
    
    # Peer DID of the node (set once at initialization)
    did = Column(String(255), nullable=True, index=True, comment="Peer DID (did:peer:1:...)")
    
    # Service endpoint for DIDComm (e.g. https://node.example.com/endpoint)
    service_endpoint = Column(String(255), nullable=True, comment="Service endpoint URL for DIDComm")
    
    # Metadata
    is_active = Column(Boolean, default=True, nullable=False, comment="Whether this key is currently active")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<NodeSettings(id={self.id}, address={self.ethereum_address})>"


class AdminUser(Base):
    """Model for storing root admin credentials (single admin only)"""
    
    __tablename__ = "admin_users"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Password authentication (optional)
    username = Column(String(255), nullable=True, unique=True, index=True, comment="Admin username")
    password_hash = Column(Text, nullable=True, comment="Hashed password (bcrypt)")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<AdminUser(id={self.id}, username={self.username})>"


class AdminTronAddress(Base):
    """Model for storing whitelisted TRON addresses for admin authentication"""
    
    __tablename__ = "admin_tron_addresses"
    
    id = Column(Integer, primary_key=True, index=True)
    tron_address = Column(String(34), unique=True, nullable=False, index=True, comment="Whitelisted TRON address")
    label = Column(String(255), nullable=True, comment="Optional label for this address")
    is_active = Column(Boolean, default=True, nullable=False, comment="Whether this address is active")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<AdminTronAddress(id={self.id}, address={self.tron_address})>"


class WalletUser(Base):
    """Model for storing wallet user profiles (non-admin users)"""
    
    __tablename__ = "wallet_users"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String(255), unique=True, nullable=False, index=True, comment="Wallet address (TRON: 34 chars, ETH: 42 chars)")
    blockchain = Column(String(20), nullable=False, index=True, comment="Blockchain type: tron, ethereum, bitcoin, etc.")
    did = Column(String(300), unique=True, nullable=False, index=True, comment="Decentralized Identifier (DID)")
    nickname = Column(String(100), nullable=False, unique=True, index=True, comment="User display name (unique)")
    avatar = Column(Text, nullable=True, comment="User avatar in base64 format (data:image/...)")
    access_to_admin_panel = Column(Boolean, default=False, nullable=False, comment="Access to admin panel")
    is_verified = Column(Boolean, default=False, nullable=False, comment="Whether the user is verified (document verification)")
    balance_usdt = Column(Numeric(20, 8), default=0, nullable=False, comment="USDT balance")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<WalletUser(id={self.id}, nickname={self.nickname})>"


class WalletUserSub(Base):
    """Sub-accounts for main app managers (linked to parent WalletUser)."""

    __tablename__ = "wallet_user_subs"

    id = Column(Integer, primary_key=True, index=True)
    wallet_user_id = Column(Integer, ForeignKey("wallet_users.id", ondelete="CASCADE"), nullable=False, index=True, comment="Parent WalletUser (manager)")
    wallet_address = Column(String(255), nullable=False, index=True, comment="Sub-account wallet address")
    blockchain = Column(String(20), nullable=False, index=True, comment="Blockchain: tron, ethereum, etc.")
    nickname = Column(String(100), nullable=True, index=True, comment="Display name for sub-account")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("wallet_user_id", "wallet_address", "blockchain", name="uq_wallet_user_sub_parent_address_chain"),)

    def __repr__(self):
        return f"<WalletUserSub(id={self.id}, nickname={self.nickname})>"


# Event listener для автоматической генерации DID при создании WalletUser
@event.listens_for(WalletUser, 'before_insert')
def generate_did_before_insert(mapper, connection, target):
    """
    Автоматически генерирует DID для нового пользователя перед вставкой в БД
    """
    if not target.did:  # Генерируем только если DID еще не установлен
        try:
            from core.utils import get_user_did
            target.did = get_user_did(target.wallet_address, target.blockchain)
        except ImportError:
            # Fallback if core.utils is not yet implemented
            target.did = f"did:ruswift:{target.blockchain}:{target.wallet_address}"


class Billing(Base):
    """Model for storing billing transactions (deposits and withdrawals)"""
    
    __tablename__ = "billing"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_user_id = Column(Integer, ForeignKey('wallet_users.id', ondelete='CASCADE'), nullable=False, index=True, comment="Reference to wallet user")
    usdt_amount = Column(Numeric(20, 8), nullable=False, comment="USDT amount: positive for deposit, negative for withdrawal")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True, comment="Transaction timestamp")
    
    def __repr__(self):
        return f"<Billing(id={self.id}, amount={self.usdt_amount})>"


class Storage(Base):
    """Model for storing JSON payloads with space-based organization"""
    
    __tablename__ = "storage"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True, comment="Autoincrement primary key")
    
    uuid = Column(UUID(as_uuid=True), unique=True, index=True, default=uuid.uuid1, nullable=False, comment="UUID v1 identifier")
    
    # Space identifier for organizing data
    space = Column(String(255), nullable=False, index=True, comment="Space identifier for organizing data")
    
    # Schema version
    schema_ver = Column(String(10), nullable=False, default="1", server_default="1", comment="Schema version")
    
    # Deal UID reference (for linking storage entries to deals)
    deal_uid = Column(String(255), nullable=True, index=True, comment="Deal UID (base58 UUID) reference")
    
    # Owner DID - пользователь, которому принадлежит ledger
    owner_did = Column(String(255), nullable=True, index=True, comment="Owner DID - пользователь, которому принадлежит ledger")
    
    # Conversation ID - для группировки сообщений в одну беседу
    conversation_id = Column(String(255), nullable=True, index=True, comment="Conversation ID для группировки сообщений")
    
    # JSON payload
    payload = Column(JSONB, nullable=False, comment="JSON payload data")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp (UTC)")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp (UTC)")
    
    # Create GIN index on JSONB payload for efficient JSON queries
    __table_args__ = (
        Index('ix_storage_payload', 'payload', postgresql_using='gin'),
    )
    
    def __repr__(self):
        return f"<Storage(id={self.id}, space={self.space})>"


class Connection(Base):
    """Model for storing DIDComm connection protocol states"""
    
    __tablename__ = "connections"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True, comment="Autoincrement primary key")
    
    # Connection identifiers
    connection_id = Column(String(255), unique=True, nullable=False, index=True, comment="Unique connection identifier (message ID)")
    my_did = Column(String(255), nullable=False, index=True, comment="Our DID")
    their_did = Column(String(255), nullable=True, index=True, comment="Their DID (null for pending invitations)")
    
    # Connection status: 'pending' or 'established'
    status = Column(String(20), nullable=False, default='pending', index=True, comment="Connection status")
    
    # Connection type: 'invitation', 'request', 'response'
    connection_type = Column(String(20), nullable=False, comment="Type of connection message")
    
    # Label for display
    label = Column(String(255), nullable=True, comment="Human-readable label")
    
    # Additional metadata (invitation_id, invitation_label, request_id, etc.)
    # Note: cannot use 'metadata' as field name - it's reserved by SQLAlchemy
    connection_metadata = Column(JSONB, nullable=True, comment="Additional connection metadata")
    
    # Original message data (stored as JSON)
    message_data = Column(JSONB, nullable=True, comment="Original DIDComm message data")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp (UTC)")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp (UTC)")
    established_at = Column(DateTime(timezone=True), nullable=True, comment="When connection was established (UTC)")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_connections_my_did_status', 'my_did', 'status'),
        Index('ix_connections_their_did_status', 'their_did', 'status'),
        Index('ix_connections_connection_metadata', 'connection_metadata', postgresql_using='gin'),
    )
    
    def __repr__(self):
        return f"<Connection(id={self.id}, status={self.status})>"


class EscrowModel(Base):
    """Model for storing multisig escrow operations and configurations"""
    
    __tablename__ = "escrow_operations"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True, comment="Autoincrement primary key")
    
    # Blockchain and network identifiers
    blockchain = Column(String(50), nullable=False, index=True, comment="Blockchain name (tron, eth, etc.)")
    network = Column(String(50), nullable=False, index=True, comment="Network name (mainnet, testnet, etc.)")
    
    # Escrow type
    escrow_type = Column(String(20), nullable=False, comment="Escrow type (multisig, contract)")
    
    # Escrow address - the address to which permissions apply
    escrow_address = Column(String(255), nullable=False, comment="Escrow address in blockchain")
    
    # Owner DID - пользователь, которому принадлежит escrow
    owner_did = Column(String(255), nullable=False, index=True, comment="Owner DID - пользователь, которому принадлежит escrow")
    
    # Participant addresses for easy searching
    participant1_address = Column(String(255), nullable=False, index=True, comment="First participant address")
    participant2_address = Column(String(255), nullable=False, index=True, comment="Second participant address")
    
    # MultisigConfig stored as JSONB
    multisig_config = Column(JSONB, nullable=False, comment="MultisigConfig configuration (JSONB)")
    
    # Address roles mapping - {"address": "role"} where role is "participant" or "arbiter"
    address_roles = Column(JSONB, nullable=False, comment="Mapping of addresses to roles (participant, arbiter)")
    
    # Arbiter address (escrow_address is initially set to arbiter address)
    arbiter_address = Column(String(255), nullable=True, comment="Arbiter address (can be changed by participants)")
    
    # Encrypted mnemonic phrase (optional)
    encrypted_mnemonic = Column(Text, nullable=True, comment="Encrypted mnemonic phrase for escrow (optional)")
    
    # Escrow status
    status = Column(
        String(50),
        nullable=False,
        default='pending',
        server_default='pending',
        index=True,
        comment="Escrow status (pending, active, inactive)"
    )

    # Адрес контракта PayoutAndFeesExecutor для атомарной выплаты (основа + комиссии); при наличии комиссионеров в сделке
    payout_executor_address = Column(String(255), nullable=True, comment="Адрес контракта PayoutAndFeesExecutor (TRON)")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp (UTC)")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp (UTC)")
    
    # Indexes and constraints
    __table_args__ = (
        # GIN index on multisig_config for efficient JSONB queries
        Index('ix_escrow_multisig_config', 'multisig_config', postgresql_using='gin'),
        # Unique constraint on blockchain, network, and escrow_address
        Index('uq_escrow_blockchain_network_address', 'blockchain', 'network', 'escrow_address', unique=True),
        # Composite index for finding escrow by participants
        Index('ix_escrow_participants', 'blockchain', 'network', 'participant1_address', 'participant2_address'),
    )
    
    def __repr__(self):
        return f"<EscrowModel(id={self.id}, address={self.escrow_address})>"


class EscrowTxnModel(Base):
    """Model for storing escrow transactions and events"""
    
    __tablename__ = "escrow_txn"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True, comment="Autoincrement primary key")
    
    # One-to-one relationship with EscrowModel
    escrow_id = Column(
        BigInteger,
        ForeignKey('escrow_operations.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to escrow operation (one-to-one)"
    )
    
    # Transaction or event data (JSONB, nullable)
    txn = Column(JSONB, nullable=True, comment="Transaction or event data (JSONB)")
    
    # Type: txn | event
    type = Column(
        String(20),
        nullable=False,
        comment="Type: 'txn' for transaction, 'event' for event"
    )
    
    # Comment (required)
    comment = Column(Text, nullable=False, comment="Comment describing the transaction or event")
    
    # Counter for duplicate events
    counter = Column(Integer, nullable=False, default=1, server_default='1', comment="Counter for duplicate events (incremented when same event occurs)")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp (UTC)")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp (UTC)")
    
    # Indexes
    __table_args__ = (
        # GIN index on txn for efficient JSONB queries
        Index('ix_escrow_txn_data', 'txn', postgresql_using='gin'),
        # Index on type for filtering
        Index('ix_escrow_txn_type', 'type'),
    )
    
    def __repr__(self):
        return f"<EscrowTxnModel(id={self.id}, type={self.type})>"


class Deal(Base):
    """Model for storing deals with base58 UUID identifier"""
    
    __tablename__ = "deal"
    
    # Primary key - autoincrement bigint
    pk = Column(BigInteger, primary_key=True, autoincrement=True, index=True, comment="Autoincrement primary key")
    
    # Base58 UUID identifier (unique, indexed)
    uid = Column(String(255), unique=True, nullable=False, index=True, comment="Base58 UUID identifier (primary identifier)")
    
    # DID identifiers for participants
    sender_did = Column(String(255), nullable=False, index=True, comment="Sender DID (owner of the deal)")
    receiver_did = Column(String(255), nullable=False, index=True, comment="Receiver DID")
    arbiter_did = Column(String(255), nullable=False, index=True, comment="Arbiter DID")
    
    # Reference to escrow operation (nullable)
    escrow_id = Column(BigInteger, ForeignKey('escrow_operations.id', ondelete='SET NULL'), nullable=True, index=True, comment="Reference to escrow operation")
    
    # Label - text description of the deal
    label = Column(Text, nullable=False, comment="Text description of the deal")
    
    # Description - дополнительное описание сделки (опционально)
    description = Column(Text, nullable=True, comment="Описание сделки (дополнительное описание, отдельно от label)")
    
    # Amount - сумма сделки (для построения payout_txn)
    amount = Column(Numeric(20, 8), nullable=True, comment="Сумма сделки")
    
    # Комиссионеры для выплаты через PayoutAndFeesExecutor: [{"address": "T...", "amount": 123}, ...], amount в наименьших единицах
    commissioners = Column(JSONB, nullable=True, comment="Комиссионеры: массив {address, amount} для атомарной выплаты (основа + комиссии)")
    
    # Current requisites (JSONB for flexibility) - текущие реквизиты сделки
    requisites = Column(JSONB, nullable=True, comment="Текущие реквизиты сделки (ФИО, назначение, валюта и др.)")
    
    # Current attachments (JSONB array of file references) - ссылки на файлы в Storage
    attachments = Column(JSONB, nullable=True, comment="Ссылки на файлы в Storage (массив объектов с uuid, name, type и др.)")
    
    # Need receiver approval flag
    need_receiver_approve = Column(Boolean, nullable=False, server_default='false', default=False, comment="Требуется ли одобрение получателя")
    
    # Deal status: wait_deposit, processing, success, appeal, wait_arbiter, recline_appeal, resolving_sender, resolving_receiver, resolved_sender, resolved_receiver
    status = Column(
        String(50),
        nullable=False,
        server_default='wait_deposit',
        default='wait_deposit',
        index=True,
        comment="Статус сделки: wait_deposit, processing, success, appeal, wait_arbiter, recline_appeal, resolving_sender, resolving_receiver, resolved_sender, resolved_receiver"
    )
    
    # Offline payout transaction (JSONB): unsigned_tx, contract_data, signatures, etc.; null when appeal or no escrow
    payout_txn = Column(
        JSONB,
        nullable=True,
        comment="Оффлайн-транзакция выплаты по сделке (зависит от status); null при appeal или без эскроу"
    )
    
    # Hash транзакции депозита в эскроу (для отслеживания)
    deposit_txn_hash = Column(String(66), nullable=True, index=True, comment="Hash транзакции депозита в эскроу")
    
    # Hash подтверждённой транзакции выплаты (заполняется при success/resolved_sender/resolved_receiver)
    payout_txn_hash = Column(String(66), nullable=True, index=True, comment="Hash подтверждённой транзакции выплаты")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp (UTC)")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp (UTC)")
    
    # Indexes for efficient queries
    __table_args__ = (
        # Indexes on participant DIDs for efficient queries
        Index('ix_deal_sender_did', 'sender_did'),
        Index('ix_deal_receiver_did', 'receiver_did'),
        Index('ix_deal_arbiter_did', 'arbiter_did'),
        Index('ix_deal_escrow_id', 'escrow_id'),
        Index('ix_deal_status', 'status'),
        # GIN indexes on requisites and attachments for efficient JSONB queries
        Index('ix_deal_requisites', 'requisites', postgresql_using='gin'),
        Index('ix_deal_attachments', 'attachments', postgresql_using='gin'),
    )
    
    def __repr__(self):
        return f"<Deal(uid={self.uid}, status={self.status})>"


class Advertisement(Base):
    """Model for storing user advertisements (offers) on marketplace"""
    
    __tablename__ = "advertisements"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True, comment="Autoincrement primary key")
    
    # Owner of the advertisement
    user_id = Column(BigInteger, nullable=False, index=True, comment="User ID from wallet_users table")
    
    # Advertisement details (based on agent cards from index.html)
    name = Column(String(255), nullable=False, comment="Display name for the advertisement")
    description = Column(Text, nullable=False, comment="Detailed description of the offer")
    
    # Financial details
    fee = Column(String(10), nullable=False, comment="Fee percentage (e.g. '2.5')")
    min_limit = Column(Integer, nullable=False, comment="Minimum transaction limit in USDT")
    max_limit = Column(Integer, nullable=False, comment="Maximum transaction limit in USDT")
    currency = Column(String(10), nullable=False, comment="Currency code (USD, EUR, RUB, etc.)")
    
    # Status and verification
    is_active = Column(Boolean, default=True, nullable=False, comment="Whether the advertisement is active")
    is_verified = Column(Boolean, default=False, nullable=False, comment="Whether the advertisement is verified by admin")
    escrow_enabled = Column(Boolean, default=False, nullable=False, comment="Whether escrow deals are enabled (agent conducts deal using their liquidity, debiting funds from escrow address upon service delivery)")
    
    # Statistics (for display purposes)
    rating = Column(String(10), nullable=True, default="0.0", comment="User rating (e.g. '4.9')")
    deals_count = Column(Integer, nullable=False, default=0, comment="Number of completed deals")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp (UTC)")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp (UTC)")
    
    # Indexes
    __table_args__ = (
        Index('ix_advertisements_user_active', 'user_id', 'is_active'),
        Index('ix_advertisements_currency_active', 'currency', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Advertisement(id={self.id}, name={self.name})>"


class Wallet(Base):
    """Model for storing encrypted wallet mnemonics and addresses"""
    
    __tablename__ = "wallets"
    
    # Table constraints - unique addresses per role and owner
    __table_args__ = (
        UniqueConstraint('tron_address', 'role', 'owner_did', name='uq_wallets_tron_address_role'),
        UniqueConstraint('ethereum_address', 'role', 'owner_did', name='uq_wallets_ethereum_address_role'),
        Index('ix_wallets_tron_address', 'tron_address'),
        Index('ix_wallets_ethereum_address', 'ethereum_address'),
        Index('ix_wallets_role', 'role'),
    )
    
    id = Column(Integer, primary_key=True, index=True, comment="Primary key")
    
    # Owner DID (node that owns this wallet; set from NodeSettings.did)
    owner_did = Column(String(255), nullable=True, index=True, comment="Owner node DID (did:peer:1:...)")
    
    # Wallet name (editable)
    name = Column(String(255), nullable=False, comment="Wallet name (editable)")
    
    # Encrypted mnemonic phrase
    encrypted_mnemonic = Column(Text, nullable=False, comment="Encrypted mnemonic phrase")
    
    # Blockchain addresses (unique per role and owner_did, not globally unique)
    tron_address = Column(String(34), nullable=False, comment="TRON address")
    ethereum_address = Column(String(42), nullable=False, comment="Ethereum address")
    
    # TRON account permissions (from blockchain)
    account_permissions = Column(JSON, nullable=True, comment="TRON account permissions from blockchain")
    
    # Wallet role
    role = Column(String(255), nullable=True, comment="Wallet role")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Creation timestamp (UTC)")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Last update timestamp (UTC)")
    
    def __repr__(self):
        return f"<Wallet(id={self.id}, name={self.name}, role={self.role})>"
