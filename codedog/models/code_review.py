from pydantic import BaseModel

from codedog.models.change_file import ChangeFile


class CodeReview(BaseModel):
    file: ChangeFile
    review: str
