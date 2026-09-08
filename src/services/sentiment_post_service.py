from src.model.user import User
from src.repositories.sentiment_post_repository import SentimentPostRepository
from src.response.expert_source_response import SentimentPostListResponse, SentimentPostResponse


class SentimentPostService:
    def __init__(self, repository: SentimentPostRepository) -> None:
        self.repository = repository

    def list_feed(self, *, current_user: User, skip: int, limit: int) -> SentimentPostListResponse:
        rows = self.repository.list_for_user_enabled_sources(user_id=current_user.id, skip=skip, limit=limit)
        return SentimentPostListResponse(total=self.repository.count_for_user_enabled_sources(user_id=current_user.id), skip=skip, limit=limit, items=[SentimentPostResponse(post_id=row.id, expert_source_id=row.expert_source_id, source_key=row.source_key, title=row.title, content=row.content, author_name=row.author_name, author_handle=row.author_handle, url=row.url, published_at=row.published_at, fetched_at=row.fetched_at, content_type=row.content_type, language=row.language) for row in rows])