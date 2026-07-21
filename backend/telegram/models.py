from pydantic import BaseModel, Field


class User(BaseModel):
    id: int
    is_bot: bool = False
    first_name: str = ""
    username: str | None = None
    language_code: str | None = None


class Chat(BaseModel):
    id: int
    type: str
    first_name: str | None = None
    username: str | None = None


class Message(BaseModel):
    model_config = {"populate_by_name": True}

    message_id: int
    from_: User | None = Field(None, alias="from")
    chat: Chat
    date: int
    text: str | None = None


class CallbackQuery(BaseModel):
    model_config = {"populate_by_name": True}

    id: str
    from_: User = Field(alias="from")
    message: Message | None = None
    data: str | None = None


class Update(BaseModel):
    update_id: int
    message: Message | None = None
    callback_query: CallbackQuery | None = None
