"""
Sovereign Study Engine v2 - Unified Spaced Repetition and Active Recall.
"""
from ..memory.sovereign_study_fts5 import StudyFTS5Index
from ..memory.fsrs_rs_bridge import FSRSEngineBridge

class SovereignStudyEngine:
    def __init__(self, db_path: str = ":memory:"):
        self.index = StudyFTS5Index(db_path)
        self.fsrs = FSRSEngineBridge(target_retention=0.90)

    def ingest_concept(self, domain: str, topic: str, content: str):
        return self.index.insert_card(domain=domain, topic=topic, content=content)

    def review_query(self, query: str):
        return self.index.search(query)
