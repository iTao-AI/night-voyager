import pytest

from night_voyager.collaboration.errors import CollaborationError
from night_voyager.collaboration.postgres import PostgresCollaborationRepository
from tests.unit.collaboration.test_postgres import db_error


def test_sqlstate_intake_unavailable_is_bounded_and_retains_public_meaning() -> None:
    with pytest.raises(CollaborationError) as error:
        PostgresCollaborationRepository._raise_mapped(  # pyright: ignore[reportPrivateUsage]
            db_error("NV027"),
            stale_error=None,
            terminal_error=False,
            invalid_message=False,
            thread_full=False,
        )
    assert str(error.value) == "intake_evidence_unavailable"


def test_intake_source_failure_is_a_safe_409_http_problem() -> None:
    import json

    from night_voyager.collaboration.errors import IntakeEvidenceUnavailableError
    from night_voyager.interfaces.http.collaboration import (
        _runtime_problem,  # pyright: ignore[reportPrivateUsage]
    )

    response = _runtime_problem(IntakeEvidenceUnavailableError("private database details"))
    assert response.status_code == 409
    body = json.loads(bytes(response.body))
    assert body["code"] == "intake_evidence_unavailable"
    assert "private database details" not in str(body)
