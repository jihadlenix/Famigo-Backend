from pydantic import BaseModel
class ORMModel(BaseModel):
    model_config = dict(from_attributes=True)
