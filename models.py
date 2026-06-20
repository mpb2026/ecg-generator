from pydantic import BaseModel

class ECGCase(BaseModel):
    id: str
    title: str
    description: str
    diagnosis: str
    explanation: str
    ecgConfig: dict
    ecg_image_url: str | None = None
