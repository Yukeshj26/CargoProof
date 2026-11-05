from pydantic import BaseModel, Field, field_validator
from typing import Optional

class ShipmentInput(BaseModel):
    container_number: str = Field(min_length=4,max_length=20)
    vessel_imo: Optional[str] = Field(default=None,pattern=r'^\d{7}$')
    booking_number: Optional[str] = Field(default=None,max_length=80)
    bill_of_lading: Optional[str] = Field(default=None,max_length=80)
    origin_port: Optional[str] = Field(default=None,max_length=120)
    destination_port: Optional[str] = Field(default=None,max_length=120)
    cargo_description: Optional[str] = Field(default=None,max_length=500)
    expected_departure: Optional[str] = None
    expected_arrival: Optional[str] = None
    declared_cargo_value_usd: Optional[float] = Field(default=None,ge=0,le=1_000_000_000)
    beneficiary_address: Optional[str] = None
    claimed_status: Optional[str] = Field(default='IN_TRANSIT',max_length=40)

    @field_validator('container_number')
    @classmethod
    def normalize_container(cls,value):return value.strip().upper()

    @field_validator('vessel_imo','booking_number','bill_of_lading','origin_port','destination_port','cargo_description','expected_departure','expected_arrival','beneficiary_address',mode='before')
    @classmethod
    def empty_optional_to_none(cls,value):return None if value is None or (isinstance(value,str) and not value.strip()) else value

class PaymentVerifyInput(BaseModel):
    quote_id: str
    tx_hash: str = Field(min_length=66,max_length=66,pattern=r'^0x[a-fA-F0-9]{64}$')
    wallet_address: str = Field(min_length=42,max_length=42,pattern=r'^0x[a-fA-F0-9]{40}$')

from uuid import uuid4
class EscrowRegisterInput(BaseModel):
    app_id: int = Field(gt=0)
    beneficiary: str = Field(min_length=58,max_length=58)
    evidence_hash: Optional[str] = Field(default=None,pattern=r'^[a-fA-F0-9]{64}$')
    amount_base_units: Optional[int] = Field(default=None,ge=0)
    nonce: str = Field(default_factory=lambda:str(uuid4()),min_length=16,max_length=80)
