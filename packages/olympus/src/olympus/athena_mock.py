"""Deterministic mock outputs for Athena pipeline (no API key)."""

from __future__ import annotations

from pydantic import BaseModel

from olympus.athena_state import (
    AnalyticalExplanations,
    AssembledStandards,
    AthenaAreteOutput,
    AthenaAsclepiusOutput,
    AthenaDaedalusOutput,
    AthenaIrisOutput,
    AthenaLetheOutput,
    AthenaNikeOutput,
    AthenaOrchestratorOutput,
    AthenaPallasOutput,
    AthenaTycheOutput,
    ChangeBoundary,
    ChangeClassification,
    ContextPackage,
    Decomposition,
    GapRegister,
    IndexStatus,
    PackageScore,
    PatternLibrary,
    RetrievedCode,
    TestingContracts,
)


def mock_athena_output(output_model: type[BaseModel], state: BaseModel) -> BaseModel:
    data = state.model_dump()
    story = str(data.get("user_story", "change"))
    repo = str(data.get("repo_path", "."))

    if output_model is AthenaLetheOutput:
        return AthenaLetheOutput(
            index_status=IndexStatus(
                ready=True,
                merkle_root="mock_merkle",
                indexed_chunks=42,
                note=f"mock index for {repo}",
            )
        )
    if output_model is AthenaIrisOutput:
        return AthenaIrisOutput(
            analytical_explanations=AnalyticalExplanations(
                summary=f"Explained modules for: {story[:80]}",
                modules=["src/main.py", "src/lib.py"],
            )
        )
    if output_model is AthenaPallasOutput:
        return AthenaPallasOutput(
            pattern_library=PatternLibrary(
                summary="Common layering and naming patterns.",
                patterns=[{"name": "service_layer", "confidence": 0.9}],
            )
        )
    if output_model is AthenaAsclepiusOutput:
        return AthenaAsclepiusOutput(
            gap_register=GapRegister(
                summary="Minor documentation gaps.",
                gap_count=1,
                gaps=[{"area": "tests", "detail": "missing edge case"}],
            )
        )
    if output_model is AthenaDaedalusOutput:
        return AthenaDaedalusOutput(
            change_boundary=ChangeBoundary(
                summary=f"Boundary around change for {story[:60]}",
                boundary_files=["src/change.py"],
            ),
            retrieved_code=RetrievedCode(
                summary="Key snippets for the change.",
                paths=["src/change.py"],
            ),
        )
    if output_model is AthenaNikeOutput:
        return AthenaNikeOutput(
            change_classification=ChangeClassification(
                change_type="refactor",
                rationale="Story implies structural cleanup without new features.",
            ),
            assembled_standards=AssembledStandards(
                summary="Apply internal style + security checklist.",
                standards=["lint", "types", "review"],
            ),
        )
    if output_model is AthenaTycheOutput:
        return AthenaTycheOutput(
            decomposition=Decomposition(
                summary="Split into implementation + tests + docs.",
                work_items=["implement", "test", "document"],
            )
        )
    if output_model is AthenaAreteOutput:
        return AthenaAreteOutput(
            testing_contracts=TestingContracts(
                summary="Contract tests for public API.",
                contracts=["happy path", "error handling"],
            )
        )
    if output_model is AthenaOrchestratorOutput:
        gaps = data.get("gap_register") or {}
        gcount = gaps.get("gap_count", 0) if isinstance(gaps, dict) else 0
        return AthenaOrchestratorOutput(
            context_package=ContextPackage(
                title=f"Context for: {story[:100]}",
                sections={
                    "standing": "index + explanations + patterns + gaps",
                    "change": "boundary + standards + decomposition + contracts",
                },
                metadata={"repo_path": repo, "gap_count": gcount},
            ),
            package_score=PackageScore(overall=0.92, notes="mock aggregate"),
        )

    raise NotImplementedError(f"No Athena mock for {output_model.__name__}")
