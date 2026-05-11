import json
import logging
from dataclasses import dataclass
from uuid import uuid4

from app.agent.intent_router import IntentRouter
from app.agent.prompts import PLANNER_SYSTEM_PROMPT, RESPONSE_SYSTEM_PROMPT
from app.models.agent import AgentIntent, AgentPlan
from app.models.build import Build, Item, ItemSummary
from app.models.chat import ChatResponse
from app.models.conversation import BuildPreferences, ConversationState
from app.services.build_crafter import BuildCraftService
from app.services.build_state import BuildStateManager
from app.services.conversation_state import ConversationStateManager
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
    use_llm: bool = True


class SoulsmithAgent:
    def __init__(
        self,
        catalog: ItemCatalog,
        rag: RagService,
        state_manager: BuildStateManager,
        conversation_manager: ConversationStateManager,
        crafter: BuildCraftService,
        openai_api_key: str | None,
        model: str,
        timeout_seconds: int,
    ):
        self.catalog = catalog
        self.rag = rag
        self.state_manager = state_manager
        self.conversation_manager = conversation_manager
        self.crafter = crafter
        self.tools = BuildTools(catalog, rag, state_manager)
        self.intent_router = IntentRouter(crafter.templates)
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

        if turn.use_llm and self.llm and HumanMessage and SystemMessage:
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
        conversation_state = self.conversation_manager.get_snapshot(conversation_id)
        context = self.tools.retrieve_context(message, limit=4)
        preferences = self.intent_router.extract_preferences(message)
        plan = await self._plan(message, current_build, context, conversation_state)

        if plan.intent == AgentIntent.reset:
            self.tools.reset_build(conversation_id)
            self.conversation_manager.reset(conversation_id)
            return PreparedTurn(
                conversation_id=conversation_id,
                build=None,
                items=[],
                response_prompt=(
                    "The user asked to reset the current build state. "
                    "Confirm the reset in one sentence."
                ),
                local_response="Build state reset. Tell me what archetype you want next.",
            )

        if plan.intent == AgentIntent.unknown:
            return PreparedTurn(
                conversation_id=conversation_id,
                build=current_build,
                items=[],
                response_prompt="The user asked for information that is not in the local dataset.",
                local_response=self._unknown_response(message),
                use_llm=False,
            )

        if plan.intent == AgentIntent.item_info:
            item = self.catalog.find_in_text(message, allow_fuzzy=True)
            return PreparedTurn(
                conversation_id=conversation_id,
                build=current_build,
                items=[self.catalog.to_summary(item)] if item else [],
                response_prompt="The user asked for item acquisition details.",
                local_response=self._item_info_response(item),
                use_llm=False,
            )

        if plan.intent == AgentIntent.clarify:
            pending_archetypes = sorted(
                self.crafter.templates.mentioned_keys(message)
                or set(conversation_state.pending_archetypes)
            )
            if not pending_archetypes and preferences.target_archetype:
                pending_archetypes = [preferences.target_archetype]
            updated_state = self.conversation_manager.update(
                conversation_id,
                preferences=preferences,
                pending_question=self.intent_router.next_clarifying_question(pending_archetypes),
                pending_archetypes=pending_archetypes,
                last_user_message=message,
            )
            return PreparedTurn(
                conversation_id=conversation_id,
                build=current_build,
                items=[],
                response_prompt=self._clarification_prompt(
                    message,
                    plan,
                    context,
                    current_build,
                    updated_state,
                ),
                local_response=self._clarification_response(message, updated_state),
            )

        if plan.intent == AgentIntent.explore:
            candidate = self._candidate_build(plan, preferences, message)
            pending_archetypes = (
                [self.crafter.templates.resolve_key(candidate.archetype, [])]
                if candidate
                else []
            )
            updated_state = self.conversation_manager.update(
                conversation_id,
                preferences=preferences,
                pending_question=self._switch_question(candidate, current_build),
                pending_archetypes=pending_archetypes,
                last_user_message=message,
            )
            items = (
                candidate.relevant_items
                if candidate
                else current_build.relevant_items if current_build else []
            )
            return PreparedTurn(
                conversation_id=conversation_id,
                build=current_build,
                items=items,
                response_prompt=self._exploration_prompt(
                    user_message=message,
                    plan=plan,
                    current_build=current_build,
                    candidate_build=candidate,
                    retrieved_context=context,
                    conversation_state=updated_state,
                ),
                local_response=self._exploration_response(message, current_build, candidate),
            )

        if current_build is None or plan.intent == AgentIntent.generate:
            if preferences.target_archetype is None and plan.archetype:
                preferences.target_archetype = plan.archetype
            self.conversation_manager.update(
                conversation_id,
                preferences=preferences,
                last_user_message=message,
            )
            self.conversation_manager.clear_pending(conversation_id)
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
        self.conversation_manager.update(conversation_id, last_user_message=message)

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
        conversation_state: ConversationState,
    ) -> AgentPlan:
        heuristic = self.intent_router.plan(message, current_build, conversation_state)
        if heuristic.intent in {
            AgentIntent.reset,
            AgentIntent.clarify,
            AgentIntent.explore,
            AgentIntent.item_info,
            AgentIntent.unknown,
        }:
            return heuristic
        if conversation_state.pending_question and heuristic.intent == AgentIntent.generate:
            return heuristic
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
                                "conversation_state": conversation_state.model_dump(),
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

    async def _complete_response(self, turn: PreparedTurn) -> str:
        if not turn.use_llm or not self.llm or not HumanMessage or not SystemMessage:
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
        conversation_state: ConversationState,
    ) -> str:
        return json.dumps(
            {
                "user_message": user_message,
                "intent": plan.model_dump(),
                "current_build": current_build.model_dump() if current_build else None,
                "conversation_state": conversation_state.model_dump(),
                "retrieved_context": retrieved_context,
                "response_requirements": [
                    "Do not generate a build yet.",
                    "Compare the likely options briefly.",
                    "Ask one focused question that helps the user choose.",
                ],
            }
        )

    def _exploration_prompt(
        self,
        user_message: str,
        plan: AgentPlan,
        current_build: Build | None,
        candidate_build: Build | None,
        retrieved_context: list[str],
        conversation_state: ConversationState,
    ) -> str:
        return json.dumps(
            {
                "user_message": user_message,
                "intent": plan.model_dump(),
                "current_build": current_build.model_dump() if current_build else None,
                "candidate_build": candidate_build.model_dump() if candidate_build else None,
                "conversation_state": conversation_state.model_dump(),
                "retrieved_context": retrieved_context,
                "response_requirements": [
                    "Discuss the candidate style without replacing the current build.",
                    "Answer direct difficulty or viability questions before asking a follow-up.",
                    "Explain the main tradeoff in practical gameplay terms.",
                    "Ask whether the user wants to switch or keep refining the current build.",
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

    def _candidate_build(
        self,
        plan: AgentPlan,
        preferences: BuildPreferences,
        message: str,
    ) -> Build | None:
        archetype = (
            plan.archetype
            or preferences.target_archetype
            or self.crafter.templates.first_mentioned_key(message)
        )
        if archetype is None:
            return None
        candidate_plan = AgentPlan(
            intent=AgentIntent.generate,
            archetype=archetype,
            constraints=plan.constraints or [message],
            item_query=plan.item_query or message,
        )
        return self.crafter.generate(candidate_plan)

    def _exploration_response(
        self,
        user_message: str,
        current_build: Build | None,
        candidate: Build | None,
    ) -> str:
        if candidate is None:
            return (
                "That direction can work, but I need one more anchor before turning it into a build. "
                "Do you want safer casting, close-range pressure, or a balanced setup?"
            )

        text = user_message.lower()
        direct_answer = self._direct_exploration_answer(candidate, text)
        tradeoff = (
            f"{candidate.archetype} leans on {candidate.equipment.weapon}"
            f" with {candidate.equipment.offhand}"
        )
        if candidate.equipment.spells:
            tradeoff += f" and {', '.join(candidate.equipment.spells)}"

        if current_build is None:
            return (
                f"{direct_answer} {tradeoff}. "
                "Want me to turn that into a full build, or compare it with another style first?"
            )

        return (
            f"{direct_answer} {tradeoff}. Compared with your {current_build.archetype}, "
            "it trades some direct pressure "
            "for more utility and timing windows. I have not changed the current build yet. "
            f"Do you want to switch toward {candidate.archetype}, or keep refining the current setup?"
        )

    def _clarification_response(self, message: str, state: ConversationState | None = None) -> str:
        mentioned = self.crafter.templates.mentioned_keys(message)
        if not mentioned and state:
            mentioned = set(state.pending_archetypes)
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

    def _switch_question(self, candidate: Build | None, current_build: Build | None) -> str:
        if candidate is None:
            return "Which combat style do you want to lean into?"
        if current_build is None:
            return f"Do you want me to turn {candidate.archetype} into a full build?"
        return f"Do you want to switch from {current_build.archetype} to {candidate.archetype}?"

    def _direct_exploration_answer(self, candidate: Build, text: str) -> str:
        if "easy" in text or "hard" in text or "beginner" in text:
            if candidate.archetype == "Faith weapon buffer":
                return (
                    "Priest-style faith is playable, but it is not the easiest first pick: "
                    "the early game is slower until the buffs and miracles come online."
                )
            if candidate.archetype == "Pyromancy bruiser":
                return (
                    "Pyromancy is one of the easier hybrid routes because spell damage "
                    "comes from flame upgrades, "
                    "not heavy stat investment."
                )
            return "It is manageable if the weapon plan fits how you like to play."

        if "good" in text or "viable" in text or "worth" in text:
            if candidate.archetype == "Pyromancy bruiser":
                return (
                    "Yes, pyromancy is very good in DS1, "
                    "especially for a flexible first or mid-game build."
                )
            if candidate.archetype == "Faith weapon buffer":
                return "Faith is good, but it pays off more once the build has its buff setup online."
            return "Yes, that direction is viable with the right stat budget."

        return "That direction can work well."

    def _unknown_response(self, message: str) -> str:
        greeting = message.lower().strip().strip("!.?,")
        if greeting in {"hi", "hello", "hey", "yo", "hola", "buenas"}:
            return (
                "Hey. I can help with Dark Souls 1 builds, stat plans, weapons, "
                "and build tweaks. Tell me what kind of run you want to try."
            )
        if greeting in {"thanks", "thank you"}:
            return "No problem. When you want to tune the build, send me the next change."

        return (
            "I don't know how to help with that yet. "
            "I'm still farming souls to reach that stat. 😅"
        )

    def _item_info_response(self, item: Item | None) -> str:
        if item is None:
            return self._unknown_response("")

        if item.acquisition:
            return f"{item.name}: {item.acquisition}"
        if item.location:
            return (
                f"{item.name} is listed around {item.location}, "
                "but I do not have the exact pickup notes yet."
            )
        if item.source_url:
            return (
                f"I have {item.name} in the local catalog, but I do not have exact pickup "
                f"notes for it yet. Source: {item.source_url}"
            )
        return self._unknown_response("")

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
