from __future__ import annotations

from pathlib import Path

from racedna.download import download_meetings, import_downloaded
from racedna.pf_api import MeetingInfo, PuntingFormClient


class FakeClient:
    def __init__(self):
        self.api_key = "test-key"

    def meetings_list(self, meeting_date, stage="A", include_barrier_trials=False):
        assert meeting_date == "2026-08-01"
        return [
            MeetingInfo(
                meeting_id=241810,
                track="Belmont Park",
                meeting_date="2026-08-01T00:00:00",
                expected_condition="Soft",
                has_sectionals=True,
            ),
            MeetingInfo(
                meeting_id=999001,
                track="Ascot",
                meeting_date="2026-08-01T00:00:00",
            ),
        ]

    def download_form_csv(self, meeting_id, race_number=0, runs=10):
        return (
            "meeting date,track,race number,horse name,form position,meeting id\n"
            f"01/08/2026 00:00:00,Belmont Park,1,Demo Horse,1,{meeting_id}\n"
        )

    def download_results_csv(self, meeting_id, race_number=0):
        # Minimal wide header/data the results importer understands
        header = (
            "MeetingId,Track,TrackId,MeetingDate,"
            "RaceResults[0].RaceId,RaceResults[0].RaceNumber,"
            "RaceResults[0].TrackConditionLabel,RaceResults[0].TrackCondition,"
            "RaceResults[0].TrackConditionNumber,RaceResults[0].OfficialRaceTime,"
            "RaceResults[0].OfficialRaceTimeString,RaceResults[0].SectionalDistance,"
            "RaceResults[0].OfficialSectionalTime,RaceResults[0].WindDirection,"
            "RaceResults[0].WindSpeed,"
            "RaceResults[0].Runners[0].Position,RaceResults[0].Runners[0].Margin,"
            "RaceResults[0].Runners[0].TabNo,RaceResults[0].Runners[0].Runner,"
            "RaceResults[0].Runners[0].RunnerId,RaceResults[0].Runners[0].Trainer,"
            "RaceResults[0].Runners[0].TrainerId,RaceResults[0].Runners[0].Jockey,"
            "RaceResults[0].Runners[0].JockeyId,RaceResults[0].Runners[0].Barrier,"
            "RaceResults[0].Runners[0].Weight,RaceResults[0].Runners[0].WeightTotal,"
            "RaceResults[0].Runners[0].WeightAllocated,RaceResults[0].Runners[0].WeightAdjustment,"
            "RaceResults[0].Runners[0].InRun,RaceResults[0].Runners[0].Flucs,"
            "RaceResults[0].Runners[0].Price,RaceResults[0].Runners[0].GearChanges,"
            "RaceResults[0].Runners[0].StewardsReports,RaceResults[0].Runners[0].StewardsReportsExt,"
            "RaceResults[0].Runners[0].FormId,RaceResults[0].Runners[0].JockeyClaim,"
            "RaceResults[0].Runners[0].OriginalBarrier,"
            "RaceResults[0].WeightType,RaceResults[0].LimitWeight,"
            "RaceResults[0].Distance,RaceResults[0].RaceClass"
        )
        data = (
            f"{meeting_id},Belmont Park,377,8/1/2026 12:00:00 AM,"
            "1359789,1,Soft,Soft,5,00:01:11.6000000,01:11.60,600,34.96,180,15,"
            "1,0.0,1,Demo Horse,1001,Trainer,1,Jockey,1,1,"
            "58,58,58,0,finish 1,opening 2.0,2.0,,,,1,0,1,"
            "Handicap,54,1200,BenchMark 66"
        )
        return header + "\n" + data + "\n"

    def download_meeting_csv(self, meeting_id, stage="A"):
        return "meetingId,track\n" f"{meeting_id},Belmont Park\n"

    def download_ratings_csv(self, meeting_id):
        return "meetingId,rating\n" f"{meeting_id},100\n"

    def download_sectionals_csv(self, meeting_id):
        return "meetingId,l6\n" f"{meeting_id},34.2\n"


def test_download_filters_track_and_writes_files(tmp_path: Path):
    out = tmp_path / "inbox"
    report = download_meetings(
        meeting_date="2026-08-01",
        track="Belmont",
        out_dir=out,
        client=FakeClient(),  # type: ignore[arg-type]
        include_form=True,
        include_results=True,
        include_meeting=False,
    )
    assert len(report.meetings) == 1
    assert report.meetings[0]["meeting_id"] == 241810
    ok_files = [f for f in report.files if f.ok]
    assert {f.kind for f in ok_files} == {"form", "results"}
    for f in ok_files:
        assert Path(f.path).exists()
        assert "Belmont_Park_241810" in f.path


def test_download_and_import(tmp_path: Path):
    out = tmp_path / "inbox"
    db = tmp_path / "t.db"
    report = download_meetings(
        meeting_date="01/08/2026",
        track="Belmont Park",
        out_dir=out,
        client=FakeClient(),  # type: ignore[arg-type]
    )
    imported = import_downloaded(report, db_path=str(db))
    types = {row["type"] for row in imported}
    assert "meeting" in types
    assert "results" in types


def test_meetings_list_payload_parsing():
    payload = {
        "payLoad": [
            {
                "meetingId": "241810",
                "track": {"name": "Belmont Park"},
                "meetingDate": "2026-08-01T00:00:00",
                "railPosition": "+6m Entire",
                "hasSectionals": True,
            }
        ]
    }

    class Client(PuntingFormClient):
        def __init__(self):
            self.api_key = "x"
            self.base_url = "https://example.test"
            self.timeout = 5

        def get_json(self, path, params=None):
            assert "meetingslist" in path
            return payload

    meetings = Client().meetings_list("2026-08-01")
    assert meetings[0].meeting_id == 241810
    assert meetings[0].track == "Belmont Park"
    assert meetings[0].rail == "+6m Entire"
