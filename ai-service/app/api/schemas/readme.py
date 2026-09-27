from pydantic import BaseModel, Field


class TechStackItem(BaseModel):
    category: str
    name: str


class EnvVarItem(BaseModel):
    key: str
    description: str = ""
    default: str | None = None


class RunCommandItem(BaseModel):
    label: str
    command: str


class KeyModuleItem(BaseModel):
    path: str
    role: str


class QuickStartSection(BaseModel):
    prerequisites: list[str] = Field(default_factory=list)
    installation: list[str] = Field(default_factory=list)
    environment_variables: list[EnvVarItem] = Field(default_factory=list)
    run_commands: list[RunCommandItem] = Field(default_factory=list)


class ReadmeFileContext(BaseModel):
    path: str
    content: str = ""


class ReadmeGenerationRequest(BaseModel):
    repository_id: str = Field(min_length=1)
    repository_name: str
    owner: str
    description: str | None = None
    primary_language: str | None = None
    files: list[ReadmeFileContext] = Field(default_factory=list)
    architecture_summary: str | None = None
    existing_readme: str | None = None


class ReadmeGenerationResponse(BaseModel):
    repository_id: str
    project_name: str
    tagline: str
    overview: str
    architecture_summary: str
    tech_stack: list[TechStackItem] = Field(default_factory=list)
    quick_start: QuickStartSection
    key_modules: list[KeyModuleItem] = Field(default_factory=list)
    markdown: str
    existing_readme: str | None = None
