import json
import logging
from pathlib import Path

from app.models.build import Item
from app.services.item_catalog import ItemCatalog

try:
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
    from langchain_openai import OpenAIEmbeddings
except Exception:  # pragma: no cover - optional until dependencies are installed
    Chroma = None
    Document = None
    OpenAIEmbeddings = None

logger = logging.getLogger(__name__)


class RagService:
    def __init__(
        self,
        catalog: ItemCatalog,
        guides_path: Path,
        persist_dir: Path,
        embedding_model: str,
        openai_api_key: str | None,
    ):
        self.catalog = catalog
        self.guides_path = guides_path
        self.persist_dir = persist_dir
        self.embedding_model = embedding_model
        self.openai_api_key = openai_api_key
        self._vector_store = None
        self._lexical_docs = self._build_lexical_docs()

    def ensure_index(self) -> None:
        if not self.openai_api_key or Chroma is None or OpenAIEmbeddings is None:
            return

        try:
            embeddings = OpenAIEmbeddings(
                model=self.embedding_model,
                api_key=self.openai_api_key,
            )
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._vector_store = Chroma(
                collection_name="soulsmith_ds1_knowledge",
                embedding_function=embeddings,
                persist_directory=str(self.persist_dir),
            )
            if self._vector_store._collection.count() == 0:
                self._vector_store.add_documents(self._documents())
        except Exception as exc:
            self._vector_store = None
            logger.warning("Falling back to lexical retrieval after RAG index failure: %s", exc)

    def retrieve(self, query: str, limit: int = 4) -> list[str]:
        if self._vector_store is not None:
            docs = self._vector_store.similarity_search(query, k=limit)
            return [doc.page_content for doc in docs]
        return self._lexical_retrieve(query, limit)

    def _documents(self):
        if Document is None:
            return []

        documents = []
        for item in self.catalog.all():
            documents.append(
                Document(
                    page_content=self._item_content(item),
                    metadata={"source": "item_catalog", "id": item.id, "category": item.category},
                )
            )

        for guide in self._load_guides():
            documents.append(
                Document(
                    page_content=f"{guide['title']}: {guide['content']}",
                    metadata={"source": "build_guide", "id": guide["id"]},
                )
            )
        return documents

    def _build_lexical_docs(self) -> list[str]:
        docs = [self._item_content(item) for item in self.catalog.all()]
        docs.extend(f"{guide['title']}: {guide['content']}" for guide in self._load_guides())
        return docs

    def _lexical_retrieve(self, query: str, limit: int) -> list[str]:
        terms = {term.lower() for term in query.split() if len(term) > 2}
        if not terms:
            return self._lexical_docs[:limit]

        scored: list[tuple[int, str]] = []
        for doc in self._lexical_docs:
            lowered = doc.lower()
            score = sum(1 for term in terms if term in lowered)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [doc for _, doc in scored[:limit]]

    def _load_guides(self) -> list[dict]:
        with self.guides_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _item_content(self, item: Item) -> str:
        requirements = ", ".join(f"{stat} {value}" for stat, value in item.requirements.items()) or "none"
        scaling = ", ".join(f"{stat} {grade}" for stat, grade in item.scaling.items()) or "none"
        tags = ", ".join(item.tags)
        weight = item.weight if item.weight is not None else "unknown"
        location = item.location or "unknown"
        acquisition = item.acquisition or "unknown"
        return (
            f"{item.name} ({item.category}, weight {weight}): {item.description} "
            f"Requirements: {requirements}. Scaling: {scaling}. "
            f"Location: {location}. Acquisition: {acquisition}. Tags: {tags}."
        )
