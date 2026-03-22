"""
Database models for storing encrypted node settings
"""
from enum import Enum

from sqlalchemy import CheckConstraint, Column, Integer, BigInteger, String, Text, DateTime, Boolean, Index, Numeric, ForeignKey, event, UniqueConstraint, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ARRAY, UUID, JSONB, JSON
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
    __table_args__ = (UniqueConstraint("nickname", name="uq_wallet_users_nickname"),)

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String(255), unique=True, nullable=False, index=True, comment="Wallet address (TRON: 34 chars, ETH: 42 chars)")
    blockchain = Column(String(20), nullable=False, index=True, comment="Blockchain type: tron, ethereum, bitcoin, etc.")
    did = Column(String(300), unique=True, nullable=False, index=True, comment="Decentralized Identifier (DID)")
    nickname = Column(String(100), nullable=False, comment="User display name (unique)")
    avatar = Column(Text, nullable=True, comment="User avatar in base64 format (data:image/...)")
    profile = Column(JSONB, nullable=True, default=None, comment="Space profile: description, company_name, icon (base64)")
    access_to_admin_panel = Column(Boolean, default=False, nullable=False, comment="Access to admin panel")
    is_verified = Column(Boolean, default=False, nullable=False, comment="Whether the user is verified (document verification)")
    balance_usdt = Column(Numeric(20, 8), default=0, nullable=False, comment="USDT balance")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<WalletUser(id={self.id}, nickname={self.nickname})>"


# Enum for WalletUserSub.roles elements (stored as strings in DB)
class WalletUserSubRole(str, Enum):
    owner = "owner"
    operator = "operator"
    reader = "reader"


class WalletUserSub(Base):
    """Sub-accounts for main app managers (linked to parent WalletUser)."""

    __tablename__ = "wallet_user_subs"

    id = Column(Integer, primary_key=True, index=True)
    wallet_user_id = Column(Integer, ForeignKey("wallet_users.id", ondelete="CASCADE"), nullable=False, index=True, comment="Parent WalletUser (manager)")
    wallet_address = Column(String(255), nullable=False, index=True, comment="Sub-account wallet address")
    blockchain = Column(String(20), nullable=False, index=True, comment="Blockchain: tron, ethereum, etc.")
    nickname = Column(String(100), nullable=True, index=True, comment="Display name for sub-account")
    roles = Column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
        comment="Set of roles: owner, operator, reader",
    )
    is_verified = Column(Boolean, default=False, nullable=False, comment="Whether the sub-account is verified")
    is_blocked = Column(Boolean, default=False, nullable=False, comment="Whether the sub-account is blocked")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("wallet_user_id", "wallet_address", "blockchain", name="uq_wallet_user_sub_parent_address_chain"),
        CheckConstraint(
            "roles <@ ARRAY['owner','operator','reader']::text[]",
            name="ck_wallet_user_subs_roles_allowed",
        ),
    )

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


class BestchangeYamlSnapshot(Base):
    """Снимок экспорта BestChange (bc.yaml): хеш, meta.exported_at и тело файла в JSON."""

    __tablename__ = "bestchange_yaml_snapshots"
    __table_args__ = (UniqueConstraint("file_hash", name="uq_bestchange_yaml_snapshots_file_hash"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="Идентификатор записи")

    file_hash = Column(
        String(64),
        nullable=False,
        comment="SHA-256 (hex) содержимого файла bc.yaml",
    )
    exported_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="meta.exported_at из YAML (момент выгрузки из BestChange)",
    )
    payload = Column(
        JSONB,
        nullable=True,
        comment="Содержимое bc.yaml, распарсенное в JSON (meta, payment_methods, cities, …)",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Время сохранения записи в БД (UTC)",
    )

    def __repr__(self):
        return f"<BestchangeYamlSnapshot(id={self.id}, file_hash={self.file_hash[:12]}..., exported_at={self.exported_at})>"


class ExchangeServiceType(str, Enum):
    """Тип сервиса обмена: фиат→стейбл (on-ramp) или стейбл→фиат (off-ramp)."""

    on_ramp = "on_ramp"
    off_ramp = "off_ramp"


class ExchangeRateMode(str, Enum):
    """Способ определения курса для сервиса обмена."""

    manual = "manual"
    on_request = "on_request"
    ratios = "ratios"


class ExchangeService(Base):
    """Конфигурация сервиса обмена (on-ramp / off-ramp): валюты, курс, лимиты, формы, KYC."""

    __tablename__ = "exchange_services"
    __table_args__ = (
        Index(
            "ix_exchange_services_fiat_type_active",
            "fiat_currency_code",
            "service_type",
            "is_active",
        ),
        Index(
            "ix_exchange_services_network_contract",
            "network",
            "contract_address",
        ),
        Index(
            "ix_exchange_services_requisites_schema",
            "requisites_form_schema",
            postgresql_using="gin",
        ),
        Index(
            "ix_exchange_services_verification_req",
            "verification_requirements",
            postgresql_using="gin",
        ),
        CheckConstraint(
            "min_fiat_amount < max_fiat_amount",
            name="ck_exchange_services_fiat_amount_range",
        ),
        CheckConstraint(
            "service_type IN ('on_ramp','off_ramp')",
            name="ck_exchange_services_service_type",
        ),
        CheckConstraint(
            "rate_mode IN ('manual','on_request','ratios')",
            name="ck_exchange_services_rate_mode",
        ),
    )

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
        comment="Идентификатор конфигурации сервиса обмена",
    )

    service_type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Тип: on_ramp (фиат+залог стейблом), off_ramp (крипта→фиат)",
    )
    fiat_currency_code = Column(
        String(3),
        nullable=False,
        index=True,
        comment="Код фиатной валюты (ISO 4217)",
    )
    stablecoin_symbol = Column(
        String(32),
        nullable=False,
        comment="Символ стейблкоина (как CollateralStablecoinToken.symbol)",
    )
    network = Column(
        String(64),
        nullable=False,
        comment="Имя сети блокчейна",
    )
    contract_address = Column(
        String(128),
        nullable=False,
        comment="Адрес контракта токена",
    )
    stablecoin_base_currency = Column(
        String(3),
        nullable=True,
        comment="Базовая валюта привязки стейбла (USD, RUB, …), опционально",
    )

    rate_mode = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Режим курса: manual, on_request, ratios",
    )
    # Семантика: единиц фиата за 1 единицу стейблкоина (направление сделки задаёт service_type)
    manual_rate = Column(
        Numeric(28, 12),
        nullable=True,
        comment="Ручной курс: фиат за 1 стейбл; для rate_mode=manual",
    )
    manual_rate_valid_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="До какого момента действует ручной курс; NULL = без срока",
    )
    ratios_engine_key = Column(
        String(255),
        nullable=True,
        comment="Ключ пары/источника в движке Ratios при rate_mode=ratios",
    )
    ratios_commission_percent = Column(
        Numeric(10, 6),
        nullable=True,
        comment="Комиссия поверх котировки Ratios, %",
    )

    min_fiat_amount = Column(
        Numeric(20, 8),
        nullable=False,
        comment="Минимальная сумма сделки в фиатной валюте",
    )
    max_fiat_amount = Column(
        Numeric(20, 8),
        nullable=False,
        comment="Максимальная сумма сделки в фиатной валюте",
    )

    requisites_form_schema = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="JSON Schema (и опц. ui_hints) формы запроса реквизитов",
    )
    verification_requirements = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="KYC/KYB: тип субъекта, список документов и т.п. (JSON)",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Сервис доступен для выбора",
    )
    is_deleted = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Мягкое удаление",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Создано (UTC)",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Обновлено (UTC)",
    )

    def __repr__(self):
        return (
            f"<ExchangeService(id={self.id}, type={self.service_type}, "
            f"fiat={self.fiat_currency_code}, stable={self.stablecoin_symbol})>"
        )


class ExchangeServiceFeeTier(Base):
    """Сетка комиссий по диапазонам суммы сделки в фиате."""

    __tablename__ = "exchange_service_fee_tiers"
    __table_args__ = (
        Index("ix_exchange_fee_tiers_service_id", "exchange_service_id"),
        CheckConstraint(
            "fiat_min < fiat_max",
            name="ck_exchange_fee_tiers_fiat_range",
        ),
        CheckConstraint(
            "fee_percent >= 0",
            name="ck_exchange_fee_tiers_fee_nonnegative",
        ),
    )

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
        comment="Идентификатор строки сетки",
    )
    exchange_service_id = Column(
        BigInteger,
        ForeignKey("exchange_services.id", ondelete="CASCADE"),
        nullable=False,
        comment="Сервис обмена",
    )
    fiat_min = Column(
        Numeric(20, 8),
        nullable=False,
        comment="Нижняя граница суммы в фиате (включительно)",
    )
    fiat_max = Column(
        Numeric(20, 8),
        nullable=False,
        comment="Верхняя граница суммы в фиате (включительно или по правилу приложения)",
    )
    fee_percent = Column(
        Numeric(10, 6),
        nullable=False,
        comment="Комиссия для диапазона, %",
    )
    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Порядок отображения / разрешения при пересечениях (меньше — раньше)",
    )

    def __repr__(self):
        return (
            f"<ExchangeServiceFeeTier(id={self.id}, service_id={self.exchange_service_id}, "
            f"range={self.fiat_min}-{self.fiat_max})>"
        )


class DashboardState(Base):
    """
    Единая строка состояния дашборда (id=1): котировки по движкам и задел под другие метрики.
    Ключи в ``ratios`` — метки движков (``get_label()``), значения — списки строк пар.
    """

    __tablename__ = "dashboard_state"

    id = Column(
        Integer,
        primary_key=True,
        comment="Фиксированный идентификатор: всегда 1",
    )
    ratios = Column(
        JSONB,
        nullable=True,
        comment="Снимок котировок: dict[engine_label, list[{base, quote, pair}]]",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Время последнего обновления строки",
    )

    def __repr__(self) -> str:
        return f"<DashboardState(id={self.id}, updated_at={self.updated_at})>"


class GuarantorDirection(Base):
    """
    Направление работы гаранта в разрезе space: валюта и платёжный метод из снимка BestChange (cur, payment_code),
    текст условий и опциональная комиссия по направлению.
    """

    __tablename__ = "guarantor_directions"
    __table_args__ = (
        UniqueConstraint(
            "space",
            "currency_code",
            "payment_code",
            name="uq_guarantor_directions_space_cur_pm",
        ),
        Index("ix_guarantor_directions_space_sort", "space", "sort_order"),
    )

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
        comment="Идентификатор направления",
    )
    space = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Идентификатор space (как в URL /{space}/…)",
    )
    currency_code = Column(
        String(64),
        nullable=False,
        comment="Код валюты (поле cur из bc.yaml / BestChange)",
    )
    payment_code = Column(
        String(128),
        nullable=False,
        comment="Код платёжного метода (payment_code в bc.yaml)",
    )
    payment_name = Column(
        String(512),
        nullable=True,
        comment="Локализованное имя метода на момент сохранения (подсказка для UI)",
    )
    conditions_text = Column(
        Text,
        nullable=True,
        comment="Описание условий по направлению",
    )
    commission_percent = Column(
        Numeric(10, 6),
        nullable=True,
        comment="Комиссия гаранта по направлению, %; NULL — использовать общую настройку",
    )
    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Порядок отображения (меньше — выше)",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Создано (UTC)",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Обновлено (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<GuarantorDirection(id={self.id}, space={self.space!r}, "
            f"cur={self.currency_code}, pm={self.payment_code})>"
        )


class GuarantorProfile(Base):
    """
    Общие условия гаранта для пары (WalletUser, space): одна строка на пользователя и space.
    Направления (валюта/метод) хранятся в ``GuarantorDirection``.
    """

    __tablename__ = "guarantor_profiles"
    __table_args__ = (
        UniqueConstraint(
            "wallet_user_id",
            "space",
            name="uq_guarantor_profiles_wallet_space",
        ),
        Index("ix_guarantor_profiles_wallet_space", "wallet_user_id", "space"),
    )

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        index=True,
        comment="Идентификатор профиля гаранта",
    )
    wallet_user_id = Column(
        Integer,
        ForeignKey("wallet_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Владелец настроек гаранта в данном space",
    )
    space = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Идентификатор space (как в URL /{space}/…)",
    )
    commission_percent = Column(
        Numeric(10, 6),
        nullable=True,
        comment="Базовая комиссия гаранта для панели, %",
    )
    conditions_text = Column(
        Text,
        nullable=True,
        comment="Общие условия работы гаранта в этом space",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Создано (UTC)",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Обновлено (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<GuarantorProfile(id={self.id}, wallet_user_id={self.wallet_user_id}, "
            f"space={self.space!r})>"
        )
