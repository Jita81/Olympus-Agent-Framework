"""Athena / Repo Analyser pipeline state and per-hero output schemas (Sprint 2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from olympus.schema_registry import register_output_schema, register_state_schema


class IndexStatus(BaseModel):
    ready: bool = True
    merkle_root: str = ""
    indexed_chunks: int = 0
    note: str = ""


class AnalyticalExplanations(BaseModel):
    summary: str = ""
    modules: list[str] = Field(default_factory=list)


class PatternLibrary(BaseModel):
    summary: str = ""
    patterns: list[dict[str, Any]] = Field(default_factory=list)


class GapRegister(BaseModel):
    summary: str = ""
    gap_count: int = 0
    gaps: list[dict[str, Any]] = Field(default_factory=list)


class ChangeBoundary(BaseModel):
    summary: str = ""
    boundary_files: list[str] = Field(default_factory=list)


class RetrievedCode(BaseModel):
    summary: str = ""
    paths: list[str] = Field(default_factory=list)


class ChangeClassification(BaseModel):
    change_type: str = ""
    rationale: str = ""


class AssembledStandards(BaseModel):
    summary: str = ""
    standards: list[str] = Field(default_factory=list)


class Decomposition(BaseModel):
    summary: str = ""
    work_items: list[str] = Field(default_factory=list)


class TestingContracts(BaseModel):
    summary: str = ""
    contracts: list[str] = Field(default_factory=list)


class ContextPackage(BaseModel):
    """Structured context package (orchestrator output)."""

    title: str = ""
    sections: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PackageScore(BaseModel):
    overall: float = 1.0
    notes: str = ""


class AthenaPipelineState(BaseModel):
    """Shared state for the eight-hero Athena slice + orchestrator."""

    user_story: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    repo_path: str = "."

    index_status: IndexStatus | None = None
    analytical_explanations: AnalyticalExplanations | None = None
    pattern_library: PatternLibrary | None = None
    gap_register: GapRegister | None = None

    change_boundary: ChangeBoundary | None = None
    retrieved_code: RetrievedCode | None = None
    change_classification: ChangeClassification | None = None
    assembled_standards: AssembledStandards | None = None
    decomposition: Decomposition | None = None
    testing_contracts: TestingContracts | None = None

    context_package: ContextPackage | None = None
    package_score: PackageScore | None = None


# Output models: field names must align with state for merge-by-key.


class AthenaLetheOutput(BaseModel):
    index_status: IndexStatus


class AthenaIrisOutput(BaseModel):
    analytical_explanations: AnalyticalExplanations


class AthenaPallasOutput(BaseModel):
    pattern_library: PatternLibrary


class AthenaAsclepiusOutput(BaseModel):
    gap_register: GapRegister


class AthenaDaedalusOutput(BaseModel):
    change_boundary: ChangeBoundary
    retrieved_code: RetrievedCode


class AthenaNikeOutput(BaseModel):
    change_classification: ChangeClassification
    assembled_standards: AssembledStandards


class AthenaTycheOutput(BaseModel):
    decomposition: Decomposition


class AthenaAreteOutput(BaseModel):
    testing_contracts: TestingContracts


class AthenaOrchestratorOutput(BaseModel):
    context_package: ContextPackage
    package_score: PackageScore


def register_athena_schemas() -> None:
    """Idempotent registration for YAML `state_schema` / `output_schema` names."""

    from olympus import schema_registry as reg

    if "AthenaPipelineState" in reg._STATE_SCHEMAS:
        return

    register_state_schema("AthenaPipelineState", AthenaPipelineState)
    register_output_schema("AthenaLetheOutput", AthenaLetheOutput)
    register_output_schema("AthenaIrisOutput", AthenaIrisOutput)
    register_output_schema("AthenaPallasOutput", AthenaPallasOutput)
    register_output_schema("AthenaAsclepiusOutput", AthenaAsclepiusOutput)
    register_output_schema("AthenaDaedalusOutput", AthenaDaedalusOutput)
    register_output_schema("AthenaNikeOutput", AthenaNikeOutput)
    register_output_schema("AthenaTycheOutput", AthenaTycheOutput)
    register_output_schema("AthenaAreteOutput", AthenaAreteOutput)
    register_output_schema("AthenaOrchestratorOutput", AthenaOrchestratorOutput)
