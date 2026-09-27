from __future__ import annotations

from pydantic import BaseModel, Field


class ApplicationAnalysis(BaseModel):
    job_title: str = ""
    relevant_skills: list[str] = Field(default_factory=list)
    relevant_experience: list[str] = Field(default_factory=list)
    relevant_projects: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    summary: str = ""
    cv_recommendations: list[str] = Field(default_factory=list)
