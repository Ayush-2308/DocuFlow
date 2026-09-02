import uuid
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.categorization_agent import categorize
from agents.extraction_agent import extract_fields
from agents.ocr_agent import run_ocr
from agents.validation_agent import validate
from db.supabase_client import insert_document, update_document_status
from schemas.models import PipelineState

REVIEW_CONFIDENCE_THRESHOLD = 0.75


def intake_node(state: PipelineState) -> PipelineState:
    state = _as_state(state)
    return state.model_copy(update={"status": "intake"})


def ocr_node(state: PipelineState) -> PipelineState:
    state = _as_state(state)
    raw_text = run_ocr(state.file_path)
    return state.model_copy(update={"raw_text": raw_text, "status": "ocr"})


def extraction_node(state: PipelineState) -> PipelineState:
    state = _as_state(state)
    extracted = extract_fields(state.raw_text or "", state.doc_type_hint or "")
    return state.model_copy(update={"extracted_data": extracted, "status": "extracted"})


def validation_node(state: PipelineState) -> PipelineState:
    state = _as_state(state)
    confidence_score, validation_errors = validate(
        state.extracted_data or {},
        state.doc_type_hint or "",
    )
    return state.model_copy(
        update={
            "confidence_score": confidence_score,
            "validation_errors": validation_errors,
            "status": "validated",
        }
    )


def categorization_node(state: PipelineState) -> PipelineState:
    state = _as_state(state)
    category = categorize(state.extracted_data or {}, state.doc_type_hint or "")
    return state.model_copy(update={"category": category, "status": "categorized"})


def storage_node(state: PipelineState) -> PipelineState:
    state = _as_state(state)
    stored = state.model_copy(update={"status": "stored"})
    insert_document(stored)
    update_document_status(stored.document_id, stored.status)
    return stored


def needs_review_node(state: PipelineState) -> PipelineState:
    state = _as_state(state)
    return state.model_copy(update={"status": "needs_review"})


def route_after_validation(state: PipelineState) -> str:
    state = _as_state(state)
    score = state.confidence_score
    if state.validation_errors or score is None or score < REVIEW_CONFIDENCE_THRESHOLD:
        return "needs_review"
    return "categorization"


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("intake", intake_node)
    graph.add_node("ocr", ocr_node)
    graph.add_node("extraction", extraction_node)
    graph.add_node("validation", validation_node)
    graph.add_node("categorization", categorization_node)
    graph.add_node("storage", storage_node)
    graph.add_node("needs_review", needs_review_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "ocr")
    graph.add_edge("ocr", "extraction")
    graph.add_edge("extraction", "validation")
    graph.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "categorization": "categorization",
            "needs_review": "needs_review",
        },
    )
    graph.add_edge("categorization", "storage")
    graph.add_edge("storage", END)
    graph.add_edge("needs_review", END)
    return graph.compile()


pipeline = build_graph()


def run_pipeline(
    file_path: str,
    doc_type_hint: str | None = None,
    document_id: str | None = None,
) -> PipelineState:
    """Run the compiled document pipeline and return the final state."""
    initial = PipelineState(
        document_id=document_id or str(uuid.uuid4()),
        file_path=file_path,
        doc_type_hint=doc_type_hint,
        status="pending",
    )
    result: Any = pipeline.invoke(initial)
    return _as_state(result)


def _as_state(state: PipelineState | dict) -> PipelineState:
    if isinstance(state, PipelineState):
        return state
    return PipelineState.model_validate(state)
