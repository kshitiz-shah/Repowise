from app.api.schemas.readme import ReadmeFileContext, ReadmeGenerationRequest
from app.services.readme_service import ReadmeService


def test_readme_generation_grounded():
    service = ReadmeService()

    files = [
        ReadmeFileContext(
            path="package.json",
            content='''{
              "name": "sample-app",
              "scripts": {
                "dev": "vite",
                "build": "tsc && vite build",
                "test": "vitest"
              },
              "dependencies": {
                "react": "^18.2.0",
                "@prisma/client": "^5.0.0"
              },
              "devDependencies": {
                "typescript": "^5.0.0",
                "vite": "^5.0.0"
              }
            }''',
        ),
        ReadmeFileContext(
            path="src/config.ts",
            content='''
            const dbUrl = process.env.DATABASE_URL;
            const apiKey = process.env.API_SECRET_KEY;
            ''',
        ),
        ReadmeFileContext(
            path=".env.example",
            content='''
            DATABASE_URL=postgresql://user:pass@localhost:5432/db
            API_SECRET_KEY=your_key_here
            PORT=3000
            ''',
        ),
    ]

    req = ReadmeGenerationRequest(
        repository_id="repo-123",
        repository_name="sample-app",
        owner="test-owner",
        description="A grounded test application",
        primary_language="TypeScript",
        files=files,
    )

    resp = service.generate_readme(req)

    assert resp.repository_id == "repo-123"
    assert resp.project_name
    assert len(resp.tech_stack) >= 3
    # Verify strict grounding on environment variables
    env_keys = [ev.key for ev in resp.quick_start.environment_variables]
    assert "DATABASE_URL" in env_keys
    assert "API_SECRET_KEY" in env_keys
    # Verify strict grounding on run commands
    cmd_labels = [c.command for c in resp.quick_start.run_commands]
    assert "npm run dev" in cmd_labels or "npm run build" in cmd_labels
    # Verify markdown output contains badges and headers
    assert "# sample-app" in resp.markdown or "# " in resp.markdown
    assert "## 🛠️ Tech Stack" in resp.markdown
    assert "## ⚙️ Environment Configuration" in resp.markdown


def test_readme_generation_tech_stack_always_present_even_without_manifest():
    service = ReadmeService()

    files = [
        ReadmeFileContext(
            path="src/main.rs",
            content='fn main() { println!("Hello world"); }',
        ),
    ]

    req = ReadmeGenerationRequest(
        repository_id="repo-999",
        repository_name="rust-cli",
        owner="rust-dev",
        description="Fast CLI tool in Rust",
        primary_language="Rust",
        files=files,
    )

    resp = service.generate_readme(req)

    assert "## 🛠️ Tech Stack" in resp.markdown
    assert "Rust" in resp.markdown
    # Verify table formatting
    assert "| Category | Technology |" in resp.markdown
    assert "- [Tech Stack](#-tech-stack)" in resp.markdown

