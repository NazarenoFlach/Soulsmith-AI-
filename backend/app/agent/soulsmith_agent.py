import json
import logging
from dataclasses import dataclass
from uuid import uuid4

from app.agent.prompts import PLANNER_SYSTEM_PROMPT, RESPONSE_SYSTEM_PROMPT
from app.models.agent import AgentIntent, AgentPlan
from app.models.build import Build, ItemSummary
from app.models.chat import ChatResponse
from app.services.build_crafter import BuildCraftService
from app.services.build_state import BuildStateManager
from app.services.item_catalog import ItemCatalog
from app.services.rag import RagService
from app.tools.build_tools import BuildTools

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    HumanMessage = None
    SystemMessage = None
    ChatOpenAI = None

logger = logging.getLogger(__name__)


@dataclass
class PreparedTurn:
    conversation_id: str
    build: Build | None
    items: list[ItemSummary]
    response_prompt: str
    local_response: str


class SoulsmithAgent:
    def __init__(
        self,
        catalog: ItemCatalog,
        rag: RagService,
        state_manager: BuildStateManager,
        crafter: BuildCraftService,
        openai_api_key: str | None,
        model: str,
        timeout_seconds: int,
    ):
        self.catalog = catalog
        self.rag = rag
        self.state_manager = state_manager
        self.crafter = crafter
        self.tools = BuildTools(catalog, rag, state_manager)
        self.llm = self._build_llm(openai_api_key, model, timeout_seconds)

    async def respond(self, message: str, conversation_id: str | None) -> ChatResponse:
        turn = await self._prepare_turn(message, conversation_id)
        response = await self._complete_response(turn)
        return ChatResponse(
            conversation_id=turn.conversation_id,
            message=response,
            build=turn.build,
            items=turn.items,
        )

    async def stream(self, message: str, conversation_id: str | None):
        turn = await self._prepare_turn(message, conversation_id)
        yield self._sse("build", turn.build.model_dump() if turn.build else None)
        yield self._sse("items", [item.model_dump() for item in turn.items])

        if self.llm and HumanMessage and SystemMessage:
            try:
                messages = [
                    SystemMessage(content=RESPONSE_SYSTEM_PROMPT),
                    HumanMessage(content=turn.response_prompt),
                ]
                async for chunk in self.llm.astream(messages):
                    token = getattr(chunk, "content", "")
                    if token:
                        yield self._sse("message.delta", {"token": token})
                yield self._sse("done", {"conversation_id": turn.conversation_id})
                return
            except Exception:
                logger.exception("Streaming response failed; using local response")
                yield self._sse("message.delta", {"token": turn.local_response})
                yield self._sse("done", {"conversation_id": turn.conversation_id})
                return

        yield self._sse("message.delta", {"token": turn.local_response})
        yield self._sse("done", {"conversation_id": turn.conversation_id})

    async def _prepare_turn(self, message: str, conversation_id: str | None) -> PreparedTurn:
        conversation_id = conversation_id or str(uuid4())
        current_build = self.state_manager.get_snapshot(conversation_id)
        context = self.tools.retrieve_context(message, limit=4)
        plan = await self._plan(message, current_build, context)

        if plan.intent == AgentIntent.reset:
            self.tools.reset_build(conversation_id)
            return PreparedTurn(
                conversation_id=conversation_id,
                build=None,
                items=[],
                response_prompt="The user asked to reset the current build state. Confirm the reset in one sentence.",
                local_response="Build state reset. Tell me what archetype you want next.",
            )

        if plan.intent == AgentIntent.clarify:
            return PreparedTurn(
                conversation_id=conversation_id,
                build=current_build,
                items=[],
                response_prompt=self._clarification_prompt(message, plan, context, current_build),
                local_response=self._clarification_response(message),
            )

        if current_build is None or plan.intent == AgentIntent.generate:
            build = self.crafter.generate(plan)
            self.state_manager.replace(conversation_id, build)
            change_summary = "Generated a new build."
        elif plan.intent == AgentIntent.refine:
            patch = self.crafter.refine(current_build, plan, message)
            build = self.state_manager.apply_patch(conversation_id, patch)
            change_summary = f"Applied this patch: {patch.model_dump(exclude_none=True)}"
        else:
            build = current_build
            change_summary = "No build fields changed."

        items = build.relevant_items if build else []
        item_context = [
            item.model_dump()
            for item in self.tools.search_items(plan.item_query or message, limit=5)
        ]
        response_prompt = self._response_prompt(
            user_message=message,
            plan=plan,
            build=build,
            retrieved_context=context,
            item_context=item_context,
            change_summary=change_summary,
        )
        local_response = self._local_response(plan, build, change_summary)
        return PreparedTurn(conversation_id, build, items, response_prompt, local_response)

    async def _plan(
        self,
        message: str,
        current_build: Build | None,
        context: list[str],
    ) -> AgentPlan:
        heuristic = self._heuristic_plan(message, current_build)
        if not self.llm or not HumanMessage or not SystemMessage:
            return heuristic

        try:
            planner = self.llm.with_structured_output(AgentPlan)
            result = await planner.ainvoke(
                [
                    SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                    HumanMessage(
                        content=json.dumps(
                            {
                                "user_message": message,
                                "has_current_build": current_build is not None,
                                "current_build": current_build.model_dump() if current_build else None,
                                "retrieved_context": context,
                            }
                        )
                    ),
                ]
            )
            return result
        except Exception:
            logger.exception("Planner failed; using heuristic plan")
            return heuristic

    def _heuristic_plan(self, message: str, current_build: Build | None) -> AgentPlan:
        text = message.lower()
        if any(term in text for term in ["reset", "start over", "clear build"]):
            return AgentPlan(intent=AgentIntent.reset)

        mentioned_archetypes = self.crafter.templates.mentioned_keys(text)
        archetype = next(iter(mentioned_archetypes), None)
        uncertainty_terms = ["not sure", "unsure", "don't know", "dont know", "maybe", " or ", "recommend me"]
        if current_build is None and (
            len(mentioned_archetypes) > 1 or any(term in text for term in uncertainty_terms)
        ):
            return AgentPlan(
                intent=AgentIntent.clarify,
                archetype=archetype,
                constraints=[message],
                item_query=message,
            )

        refine_terms = ["lighter", "faster", "swap", "change", "more poise", "tankier", "shield", "fast roll"]
        if current_build and any(term in text for term in refine_terms):
            return AgentPlan(
                intent=AgentIntent.refine,
                archetype=current_build.archetype,
                refinement_targets=[term for term in refine_terms if term in text],
                constraints=[message],
                item_query=message,
            )
        if current_build and any(term in text for term in ["why", "explain", "how does"]):
            return AgentPlan(intent=AgentIntent.explain, item_query=message)
        if any(term in text for term in ["recommend", "item", "weapon", "ring"]) and current_build:
            return AgentPlan(intent=AgentIntent.recommend, item_query=message)
        return AgentPlan(
            intent=AgentIntent.generate,
            archetype=archetype or "quality",
            constraints=[message],
            item_query=message,
        )

    async def _complete_response(self, turn: PreparedTurn) -> str:
        if not self.llm or not HumanMessage or not SystemMessage:
            return turn.local_response
        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=RESPONSE_SYSTEM_PROMPT),
                    HumanMessage(content=turn.response_prompt),
                ]
            )
            return str(response.content)
        except Exception:
            logger.exception("Response generation failed; using local response")
            return turn.local_response

    def _clarification_prompt(
        self,
        user_message: str,
        plan: AgentPlan,
        retrieved_context: list[str],
        current_build: Build | None,
    ) -> str:
        return json.dumps(
            {
                "user_message": user_message,
                "intent": plan.model_dump(),
                "current_build": current_build.model_dump() if current_build else None,
                "retrieved_context": retrieved_context,
                "response_requirements": [
                    "Do not generate a build yet.",
                    "Compare the likely options briefly.",
                    "Ask one focused question that helps the user choose.",
                ],
            }
        )

    def _response_prompt(
        self,
        user_message: str,
        plan: AgentPlan,
        build: Build | None,
        retrieved_context: list[str],
        item_context: list[dict],
        change_summary: str,
    ) -> str:
        return json.dumps(
            {
                "user_message": user_message,
                "intent": plan.model_dump(),
                "change_summary": change_summary,
                "current_build": build.model_dump() if build else None,
                "retrieved_context": retrieved_context,
                "candidate_items": item_context,
                "response_requirements": [
                    "Be concise.",
                    "Mention the build's core loop.",
                    "For refinements, explicitly say what changed and what stayed stable.",
                ],
            }
        )

    def _local_response(self, plan: AgentPlan, build: Build | None, change_summary: str) -> str:
        if plan.intent == AgentIntent.clarify:
            return self._clarification_response(plan.item_query or "")
        if build is None:
            return "Build state reset. Tell me the next archetype you want to explore."
        if plan.intent == AgentIntent.refine:
            return (
                f"{change_summary}. The core stat spread stays intact: "
                f"{build.stats.strength} STR, {build.stats.dexterity} DEX, "
                f"with {build.equipment.weapon} as the current weapon."
            )
        return (
            f"I built a {build.archetype}: {build.equipment.weapon}, "
            f"{build.equipment.offhand}, {build.equipment.armor}, and "
            f"{', '.join(build.equipment.rings)}. {build.playstyle}"
        )

    def _clarification_response(self, message: str) -> str:
        mentioned = self.crafter.templates.mentioned_keys(message)
        if {"dexterity", "sorcery"}.issubset(mentioned):
            return (
                "Dexterity is better if you want fast melee and bleed pressure. "
                "Sorcery is better if you want safer ranged control and spell scaling. "
                "Do you want the build to feel more close-range, ranged, or hybrid?"
            )
        return (
            "There are a couple of viable directions here. "
            "Do you prefer aggressive melee, safer ranged damage, or a balanced build?"
        )

    def _build_llm(self, api_key: str | None, model: str, timeout_seconds: int):
        if not api_key or ChatOpenAI is None:
            return None
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            timeout=timeout_seconds,
            temperature=0.4,
            streaming=True,
        )

    def _sse(self, event: str, data) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"
