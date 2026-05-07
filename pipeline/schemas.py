from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class MatrixItem(BaseModel):
    statement: str
    confidence: Literal["high", "medium", "low", "contradicted"]
    source_excerpt: str
    contradiction_note: Optional[str] = None


class MatrixRow(BaseModel):
    pain_points: List[MatrixItem] = Field(default_factory=list)
    desired_state: List[MatrixItem] = Field(default_factory=list)
    success_criteria: List[MatrixItem] = Field(default_factory=list)
    risks_unknowns: List[MatrixItem] = Field(default_factory=list)


class StakeholderProfile(BaseModel):
    name: str
    title: str
    role_in_decision: str
    stance: Literal["champion", "neutral", "skeptic", "unknown"]
    influence: Literal["high", "medium", "low"]
    key_concern: str
    source_excerpt: str


class ClientMatrix(BaseModel):
    business: MatrixRow
    technical: MatrixRow
    operational: MatrixRow
    strategic: MatrixRow
    stakeholders: List[StakeholderProfile] = Field(default_factory=list)
