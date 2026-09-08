from src.repositories.expert_source_repository import ExpertSourceRepository
from src.response.expert_source_response import ExpertSourceListResponse, ExpertSourceResponse


class ExpertSourceService:
    def __init__(self, repository: ExpertSourceRepository) -> None:
        self.repository = repository

    def list_active(self, *, skip: int, limit: int) -> ExpertSourceListResponse:
        sources = self.repository.list_active(skip=skip, limit=limit)
        return ExpertSourceListResponse(total=self.repository.count_active(), skip=skip, limit=limit, items=[ExpertSourceResponse(expert_source_id=source.id, source_key=source.source_key, author_name=source.author_name, author_handle=source.author_handle, profile_url=source.profile_url) for source in sources])