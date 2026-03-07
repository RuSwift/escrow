from pydantic import BaseModel

class BaseResource:
    
    class Create(BaseModel, extra="ignore"):
        pass
    
    class Update(BaseModel, extra="ignore"):
        pass
    
    class Patch(BaseModel, extra="ignore"):
        pass
    
    class Delete(BaseModel, extra="ignore"):
        pass
    
    class Get(BaseModel, extra="ignore"):
        pass
