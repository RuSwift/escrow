"""
Custom exceptions for the application
"""
from i18n import _


class AccessDeniedError(Exception):
    """
    Base exception for access denied errors
    
    Used when a user tries to perform an operation they don't have permission for.
    """
    
    def __init__(self, message: str, resource_id: str = None, owner_did: str = None, attempted_by: str = None):
        """
        Initialize the exception
        
        Args:
            message: Error message
            resource_id: ID of the resource access was denied to
            owner_did: DID of the resource owner
            attempted_by: DID of the user who attempted the operation
        """
        self.resource_id = resource_id
        self.owner_did = owner_did
        self.attempted_by = attempted_by
        super().__init__(message)


class DealAccessDeniedError(AccessDeniedError):
    """
    Exception raised when a user tries to edit a deal they don't own
    
    Only the deal owner (sender_did = owner_did) can edit the deal.
    Other participants can view the deal but cannot modify it.
    """
    
    def __init__(self, deal_uid: str, owner_did: str, attempted_by: str):
        """
        Initialize the exception
        
        Args:
            deal_uid: UID of the deal
            owner_did: DID of the deal owner (sender_did)
            attempted_by: DID of the user who attempted the operation
        """
        self.deal_uid = deal_uid
        message = _(
            "errors.access_denied_deal_owner",
            owner_did=owner_did,
            deal_uid=deal_uid,
            attempted_by=attempted_by,
        )
        super().__init__(
            message=message,
            resource_id=deal_uid,
            owner_did=owner_did,
            attempted_by=attempted_by
        )


class SpacePermissionDenied(Exception):
    """Выбрасывается, когда текущий пользователь не является owner спейса и запрошена операция только для owner."""


class InvalidWalletAddress(Exception):
    """Выбрасывается, когда blockchain + wallet_address не прошли проверку формата."""


class MissingNickname(Exception):
    """Участник (Sub) должен иметь непустой nickname."""


class DuplicateParticipant(Exception):
    """Участник с таким адресом кошелька и сетью уже есть в спейсе."""


class GuarantorDirectionValidationError(Exception):
    """
    Ошибка валидации при создании направления гаранта.
    ``code`` — стабильный идентификатор для i18n на клиенте (например ``all_methods_blocked_by_specific``).
    """

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or code
        super().__init__(self.message)
