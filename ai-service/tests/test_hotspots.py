from app.api.schemas.hotspots import (
    CommitHotspotInput,
    DependencyHotspotInput,
    FileHotspotInput,
    HotspotCalculationRequest,
)
from app.services.hotspot_service import HotspotService


def test_hotspot_calculation():
    service = HotspotService()

    files = [
        FileHotspotInput(id="f1", path="server/src/auth.ts", name="auth.ts", lines_of_code=250),
        FileHotspotInput(id="f2", path="server/src/db.ts", name="db.ts", lines_of_code=100),
        FileHotspotInput(id="f3", path="client/src/App.tsx", name="App.tsx", lines_of_code=500),
    ]

    commits = [
        CommitHotspotInput(sha="c1", message="fix authentication timeout bug", files=["server/src/auth.ts"]),
        CommitHotspotInput(sha="c2", message="patch crash in auth logic", files=["server/src/auth.ts", "server/src/db.ts"]),
        CommitHotspotInput(sha="c3", message="refactor auth session checks", files=["server/src/auth.ts"]),
    ]

    dependencies = [
        DependencyHotspotInput(source_path="client/src/App.tsx", target_path="server/src/auth.ts"),
        DependencyHotspotInput(source_path="server/src/db.ts", target_path="server/src/auth.ts"),
    ]

    req = HotspotCalculationRequest(
        repository_id="test-repo",
        files=files,
        commits=commits,
        bug_mappings=[],
        dependencies=dependencies,
    )

    resp = service.calculate_hotspots(req)

    assert resp.repository_id == "test-repo"
    assert len(resp.files) == 3
    # auth.ts should have the highest risk score due to churn, bug fix commits, and dependencies
    top_file = resp.files[0]
    assert top_file.path == "server/src/auth.ts"
    assert top_file.risk_score > resp.files[1].risk_score
    assert top_file.evidence.churn_commits == 3
    assert top_file.evidence.bug_fix_commits == 2
    assert top_file.evidence.in_degree == 2
    assert len(resp.components) >= 2
