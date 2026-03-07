"""
Custom exceptions for the application
"""


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
        message = (
            f"Access denied: Only the deal owner (owner_did={owner_did}) "
            f"can edit deal {deal_uid}. "
            f"Attempted by: {attempted_by}"
        )
        super().__init__(
            message=message,
            resource_id=deal_uid,
            owner_did=owner_did,
            attempted_by=attempted_by
        )
