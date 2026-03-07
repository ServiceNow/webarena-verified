from pydantic import BaseModel, Field


class EvaluationSummary(BaseModel):
    overall_score: float = Field(ge=0)
    shopping_score: float = Field(ge=0)
    reddit_score: float = Field(ge=0)
    gitlab_score: float = Field(ge=0)
    wikipedia_score: float = Field(ge=0)
    map_score: float = Field(ge=0)
    shopping_admin_score: float = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    evaluator_version: str = Field(min_length=1)
