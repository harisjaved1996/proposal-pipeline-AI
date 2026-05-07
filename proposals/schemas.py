from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class ProposalSection(BaseModel):
    title: str
    body: str
    bullets: List[str] = Field(default_factory=list)


class PhaseItem(BaseModel):
    phase_number: int
    phase_name: str
    duration: str
    deliverables: List[str]
    description: str


class OpenQuestion(BaseModel):
    question: str
    source_statement: str
    confidence: Literal["low", "contradicted"]
    dimension: Literal["business", "technical", "operational", "strategic"]


class ProposalDocument(BaseModel):
    executive_summary: ProposalSection
    understanding: ProposalSection
    approach: ProposalSection
    phases_timeline: List[PhaseItem] = Field(min_length=1)
    pricing_approach: ProposalSection
    open_questions: List[OpenQuestion] = Field(default_factory=list)
    client_name: str = ""
    total_duration_estimate: str = ""
    engagement_type: str = ""
