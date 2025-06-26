"""AI-powered solution optimizer using vector similarity search and LLM evaluation.

For every alert document this script embeds its `solution_comment`, then
performs a vector similarity search **filtered by error_code** against the
`solutions` collection. The intelligent decision process:

    score > 0.95  → duplicate detected, ignore
    0.8–0.95      → use LLM to determine if solutions should be merged or one is a subset
    < 0.8         → insert as new solution if not a subset of existing solutions

This creates an optimized, non-redundant knowledge base of manufacturing solutions.
"""

import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from couchbase.exceptions import CouchbaseException
from couchbase.mutation_state import MutationState
import couchbase.search as search
from couchbase.options import SearchOptions
from couchbase.vector_search import VectorQuery, VectorSearch

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, ValidationError

from setup.couchbase_client import CouchbaseClient
from src.config.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Constants
HIGH_SIM_THRESHOLD = 0.95
MED_SIM_THRESHOLD = 0.8
ALERTS_COLLECTION = "alerts"
SOLUTIONS_COLLECTION = "solutions"
EMBEDDING_MODEL = "models/text-embedding-004"
LLM_MODEL = "gemini-2.5-pro"


class Decision(str, Enum):
    """Decision types for LLM evaluation."""
    subset = "subset"
    extend = "extend"


class LLMResponse(BaseModel):
    """Response model for LLM decision."""
    decision: Decision
    extended_solution: Optional[str] = None


# LLM Prompts
EXTEND_PROMPT = PromptTemplate(
    template="""Compare two maintenance solutions. Return ONLY raw JSON, no formatting, no code blocks:

EXISTING: {s1}
CANDIDATE: {s2}

Tasks:
1. Check if either solution is a complete subset of the other
2. If neither is a subset, merge them without duplication

Response format:
{{
  "decision": "subset|extend",
  "extended_solution": "merged text or empty if subset"
}}""",
    input_variables=["s1", "s2"],
)

SUBSET_PROMPT = PromptTemplate(
    template="""Compare solutions. Respond with one word only:

FIRST: {s1}
SECOND: {s2}

Answer "subset" if either solution is entirely contained in the other, otherwise "not_subset".""",
    input_variables=["s1", "s2"],
)


class SolutionOptimizer:
    """Handles AI-powered optimization of manufacturing alert solutions using vector similarity and LLM evaluation."""
    
    def __init__(self):
        self.cb = CouchbaseClient()
        self.embedder = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
        self.llm: Optional[ChatGoogleGenerativeAI] = None
        self.mutation_state: Optional[MutationState] = None

    def run(self) -> None:
        """Run the solution optimization process."""
        logger.info("Beginning AI-powered solution optimization...")

        alerts = self._fetch_alert_sentences()
        if not alerts:
            logger.warning("No alert sentences found to process")
            return

        logger.info(f"Processing {len(alerts)} alert sentences...")

        for alert in alerts:
            self._process_sentence(alert["error_code"], alert["solution_comment"].strip())

        logger.info("✅ Solution optimization complete")

    def _fetch_alert_sentences(self) -> List[dict]:
        """Fetch alert sentences from the database."""
        bucket = settings.couchbase_bucket_name
        scope = settings.couchbase_scope_name
        alerts_coll = settings.couchbase_collections[ALERTS_COLLECTION]

        query = (
            f"SELECT META().id AS doc_id, error_code, solution_comment "
            f"FROM `{bucket}`.`{scope}`.`{alerts_coll}` "
            "WHERE type = 'alert' AND error_code IS NOT NULL AND solution_comment IS NOT NULL"
        )

        try:
            return list(self.cb.cluster.query(query))
        except CouchbaseException as err:
            logger.error(f"Query failed: {err}")
            return []

    def _process_sentence(self, error_code: str, sentence: str) -> None:
        """Process a single sentence for optimization."""
        logger.info("=======================")
        if not sentence:
            return
        
        logger.info(f"Processing sentence: {sentence}, error_code: {error_code}")

        # Vector similarity search filtered by error_code
        results = self._perform_similarity_search(sentence, error_code)
        
        if not results:
            # Insert as new solution
            self.mutation_state = self._insert_sentence(error_code, sentence)
            logger.info(f"Inserted new solution for error_code '{error_code}'")
            return

        best_doc = results[0]
        logger.info(f"found best doc {best_doc}")
        
        # High similarity - treat as duplicate
        if best_doc["score"] >= HIGH_SIM_THRESHOLD:
            logger.info("High similarity - treating as duplicate")
            return

        # Medium similarity - use LLM evaluation
        if MED_SIM_THRESHOLD <= best_doc["score"] < HIGH_SIM_THRESHOLD:
            self._handle_medium_similarity(best_doc, sentence)
            return

        # Low similarity - check if new sentence is subset
        if self._is_subset_only(best_doc["solution_comment"], sentence):
            logger.info("New sentence is subset of existing - ignoring")
            return

        # Insert as new solution
        self.mutation_state = self._insert_sentence(error_code, sentence)
        logger.info(f"Inserted new solution for error_code '{error_code}'")

    def _perform_similarity_search(self, sentence: str, error_code: str) -> List[dict]:
        """Perform vector similarity search with error code filter."""
        try:
            prefilter = search.TermQuery(field="error_code", term=error_code)
            return self.similarity_search_with_score(
                sentence, k=1, prefilter=prefilter, consistent_with=self.mutation_state
            )
        except Exception as exc:
            logger.error(f"Vector search failed: {exc}")
            return []

    def _handle_medium_similarity(self, best_doc: dict, sentence: str) -> None:
        """Handle medium similarity case with LLM evaluation."""
        llm_resp = self._evaluate_llm(best_doc["solution_comment"], sentence)
        if llm_resp and llm_resp.decision == Decision.subset:
            logger.info("LLM determined candidate is subset - ignoring")
            return
        
        if llm_resp and llm_resp.decision == Decision.extend and llm_resp.extended_solution:
            merged = llm_resp.extended_solution
        else:
            # Fallback: use longer sentence
            merged = sentence if len(sentence) > len(best_doc["solution_comment"]) else best_doc["solution_comment"]
        
        self.mutation_state = self._extend_sentence(best_doc["id"], merged)
        logger.info(f"Extended existing solution with merged content")

    def similarity_search_with_score(
        self, 
        query: str, 
        k: int = 1, 
        prefilter: Optional[search.SearchQuery] = None, 
        consistent_with: Optional[MutationState] = None
    ) -> List[dict]:
        """Perform vector similarity search and return results with scores."""
        embedding = self.embedder.embed_query(query)
        search_req = search.SearchRequest.create(
            VectorSearch.from_vector_query(
                VectorQuery(
                    field_name="embedding",
                    vector=embedding,
                    num_candidates=k,
                    prefilter=prefilter
                )
            )
        )
        results = self.cb.scope.search(
            f"semantic_{settings.couchbase_collections[SOLUTIONS_COLLECTION]}",
            search_req,
            SearchOptions(limit=k, fields=["*"], consistent_with=consistent_with),
        )

        docs = []
        for result in results:
            doc = {"id": result.id, "score": result.score}
            doc.update(result.fields)
            docs.append(doc)
        return docs

    def _insert_sentence(self, error_code: str, sentence: str) -> Optional[MutationState]:
        """Insert a new solution sentence."""
        try:
            emb = self.embedder.embed_query(sentence)
            doc = {
                "type": "solution",
                "error_code": error_code,
                "solution_comment": sentence,
                "embedding": emb,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            doc_id = f"solution_{error_code}_{uuid.uuid4().hex[:8]}"
            coll = self.cb.get_collection(SOLUTIONS_COLLECTION)
            result = coll.upsert(doc_id, doc)
            return MutationState(result)
        except Exception as exc:
            logger.error(f"Failed inserting sentence: {exc}")
            return None

    def _extend_sentence(self, doc_id: str, combined_sentence: str) -> Optional[MutationState]:
        """Update an existing solution with extended content."""
        try:
            coll = self.cb.get_collection(SOLUTIONS_COLLECTION)
            doc = coll.get(doc_id).content_as[dict]
            doc["solution_comment"] = combined_sentence
            doc["updated_at"] = datetime.utcnow().isoformat()
            doc["embedding"] = self.embedder.embed_query(combined_sentence)
            result = coll.upsert(doc_id, doc)
            return MutationState(result)
        except Exception as exc:
            logger.error(f"Failed updating sentence: {exc}")
            return None

    def _evaluate_llm(self, existing: str, new: str) -> Optional[LLMResponse]:
        """Use LLM to evaluate if new sentence should extend existing one."""
        if self.llm is None:
            self.llm = ChatGoogleGenerativeAI(model=LLM_MODEL)
        
        prompt = EXTEND_PROMPT.format(s1=existing, s2=new)
        try:
            raw = self.llm.invoke(prompt).content.strip()
            logger.info(f"LLM response: {raw}")
            data = json.loads(self._clean_json_response(raw))
            return LLMResponse(**data)
        except (ValidationError, json.JSONDecodeError) as exc:
            logger.error(f"LLM evaluation failed: {exc} message: {raw}")
            return None

    def _clean_json_response(self, response: str) -> str:
        """Remove markdown formatting from JSON response."""
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]  # Remove ```json
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]   # Remove ```
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]  # Remove trailing ```
        return cleaned.strip()

    def _is_subset_only(self, s1: str, s2: str) -> bool:
        """Return True if s2 is subset of s1 using simple LLM prompt."""
        if self.llm is None:
            self.llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0.0)
        
        prompt = SUBSET_PROMPT.format(s1=s1, s2=s2)
        try:
            resp = self.llm.invoke(prompt).content.strip().lower()
            return resp.startswith("subset")
        except Exception as exc:
            logger.error(f"Subset evaluation failed: {exc}")
            # Fallback: simple length comparison
            return len(s2) < len(s1)


if __name__ == "__main__":
    SolutionOptimizer().run() 