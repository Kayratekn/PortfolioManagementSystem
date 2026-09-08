from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError

from src.integrations.ai_client import (
    AiClient,
    AiServiceRequestError,
    AiServiceResponseError,
    AiServiceUnavailableError,
)
from src.model.report_chunk import ReportChunk
from src.model.report_document import ReportDocument
from src.model.user import User
from src.repositories.report_repository import ReportRepository
from src.response.report_qa_response import ReportQaAiResult, ReportQaCitation, ReportQaResponse
from src.services.ai_analysis_persistence_service import AiAnalysisPersistenceService


REPORT_QA_ENDPOINT = "/api/ai/report-qa"


class ReportQaService:
    def __init__(
        self,
        *,
        report_repository: ReportRepository,
        ai_client: AiClient,
        persistence_service: AiAnalysisPersistenceService,
    ) -> None:
        self.report_repository = report_repository
        self.ai_client = ai_client
        self.persistence_service = persistence_service

    def answer_question(
        self,
        *,
        report_id: int,
        query: str,
        current_user: User,
    ) -> ReportQaResponse:
        report = self.report_repository.get_document_by_id_for_user(
            report_id=report_id,
            user_id=current_user.id,
        )
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found.",
            )

        chunks = self.report_repository.list_chunks_by_document_id(
            report_document_id=report.id,
        )
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Report has no content available for Q&A.",
            )

        ai_result = self._validate_ai_response(
            self._call_ai_service(
                self._build_ai_payload(
                    user_id=current_user.id,
                    query=query,
                    report=report,
                    chunks=chunks,
                )
            )
        )
        self._validate_citations(
            citations=ai_result.citations,
            report=report,
            chunks=chunks,
        )
        serialized_result = ai_result.model_dump(mode="json")
        analysis = self.persistence_service.persist_analysis(
            user_id=current_user.id,
            portfolio_id=None,
            analysis_type="report-qa",
            result_payload={
                "report_id": report.id,
                "citations": serialized_result["citations"],
                "confidence_score": serialized_result["confidence_score"],
                "suggested_followups": serialized_result["suggested_followups"],
            },
            explanation_text=ai_result.answer,
            disclaimer=ai_result.disclaimer,
            model_version=ai_result.model_version,
            formula_version=None,
        )
        return ReportQaResponse(
            analysis_id=analysis.id,
            report_id=report.id,
            **serialized_result,
        )

    @staticmethod
    def _build_ai_payload(
        *,
        user_id: int,
        query: str,
        report: ReportDocument,
        chunks: list[ReportChunk],
    ) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "query": query,
            "report_ids": [report.id],
            "report_chunks": [
                {
                    "report_id": report.id,
                    "report_name": report.original_filename,
                    "chunk_id": chunk.id,
                    "page_number": chunk.page_number,
                    "text": chunk.text,
                }
                for chunk in chunks
            ],
        }

    @staticmethod
    def _validate_citations(
        *,
        citations: list[ReportQaCitation],
        report: ReportDocument,
        chunks: list[ReportChunk],
    ) -> None:
        chunks_by_id = {chunk.id: chunk for chunk in chunks}
        for citation in citations:
            chunk = chunks_by_id.get(citation.chunk_id)
            if (
                citation.report_id != report.id
                or chunk is None
                or citation.page_number != chunk.page_number
                or citation.report_name != report.original_filename
            ):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="AI service returned an invalid response.",
                )
    def _call_ai_service(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.ai_client.post_json(REPORT_QA_ENDPOINT, payload)
        except AiServiceUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service temporarily unavailable.",
            ) from exc
        except AiServiceRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service rejected the backend request.",
            ) from exc
        except AiServiceResponseError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service returned an invalid response.",
            ) from exc

    @staticmethod
    def _validate_ai_response(response: dict[str, Any]) -> ReportQaAiResult:
        try:
            return ReportQaAiResult.model_validate(response)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service returned an invalid response.",
            ) from exc
