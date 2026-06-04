import re
from difflib import SequenceMatcher

from app.models.agent import AgentIntent, AgentPlan
from app.models.build import Build
from app.models.conversation import BuildPreferences, ConversationState
from app.services.build_templates import BuildTemplateCatalog


ITEM_FACT_ACTION_WORDS = {
    "boost",
    "buff",
    "cure",
    "damage",
    "drop",
    "farm",
    "find",
    "get",
    "heal",
    "hit",
    "improve",
    "improves",
    "increase",
    "lets",
    "location",
    "obtain",
    "open",
    "reinforce",
    "unlock",
    "upgrade",
    "where",
}
ITEM_FACT_NOUNS = {
    "armor",
    "ember",
    "item",
    "key",
    "material",
    "miracle",
    "pyromancy",
    "ring",
    "shield",
    "sorcery",
    "spell",
    "thing",
    "weapon",
}
ITEM_FACT_QUESTION_WORDS = {"how", "what", "where", "which"}


class IntentRouter:
    def __init__(self, templates: BuildTemplateCatalog):
        self.templates = templates

    def plan(
        self,
        message: str,
        current_build: Build | None,
        state: ConversationState,
    ) -> AgentPlan:
        text = message.lower()
        if any(term in text for term in ["reset", "start over", "clear build"]):
            return AgentPlan(intent=AgentIntent.reset)

        if self._looks_like_greeting(text):
            return AgentPlan(
                intent=AgentIntent.unknown,
                constraints=[message],
                item_query=message,
            )

        if self._looks_like_item_fact_question(text):
            return AgentPlan(
                intent=AgentIntent.item_info,
                constraints=[message],
                item_query=message,
            )

        preferences = self.extract_preferences(message)
        pending_archetype = self._single_pending_archetype(state)
        if state.pending_question and pending_archetype and self._looks_like_confirmation(text):
            return AgentPlan(
                intent=AgentIntent.generate,
                archetype=pending_archetype,
                constraints=[message, f"confirmed_from={state.last_user_message or 'pending'}"],
                item_query=message,
            )

        resolved_archetype = self._resolve_pending_archetype(preferences, state)
        if current_build is None and state.pending_question and resolved_archetype:
            return AgentPlan(
                intent=AgentIntent.generate,
                archetype=resolved_archetype,
                constraints=[
                    message,
                    f"play_style={preferences.play_style or state.preferences.play_style}",
                ],
                item_query=message,
            )

        mentioned_archetypes = self.templates.mentioned_keys(text)
        archetype = self.templates.first_mentioned_key(text)
        if len(mentioned_archetypes) == 1 and archetype and self._looks_like_exploration(text):
            return AgentPlan(
                intent=AgentIntent.explore,
                archetype=archetype,
                constraints=[message],
                item_query=message,
            )

        uncertainty_terms = [
            "not sure",
            "unsure",
            "don't know",
            "dont know",
            "dont be sure",
            "maybe",
            " or ",
            "between",
            "recommend me",
        ]
        if current_build is None and (
            len(mentioned_archetypes) > 1
            or (not archetype and any(term in text for term in uncertainty_terms))
        ):
            return AgentPlan(
                intent=AgentIntent.clarify,
                archetype=archetype,
                constraints=[message],
                item_query=message,
            )

        if archetype and self._looks_like_switch_request(text):
            return AgentPlan(
                intent=AgentIntent.generate,
                archetype=archetype,
                constraints=[message],
                item_query=message,
            )

        if archetype and self._looks_like_exploration(text):
            return AgentPlan(
                intent=AgentIntent.explore,
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

        if archetype:
            return AgentPlan(
                intent=AgentIntent.generate,
                archetype=archetype,
                constraints=[message],
                item_query=message,
            )

        if current_build is None and self._looks_like_build_request(text):
            return AgentPlan(
                intent=AgentIntent.clarify,
                constraints=[message],
                item_query=message,
            )

        return AgentPlan(
            intent=AgentIntent.unknown,
            constraints=[message],
            item_query=message,
        )

    def extract_preferences(self, message: str) -> BuildPreferences:
        text = message.lower()
        mentioned = self.templates.mentioned_keys(text)

        play_style = None
        if any(term in text for term in ["hybrid", "both", "some magic", "melee and magic"]):
            play_style = "hybrid"
        elif any(term in text for term in ["ranged", "range", "spell", "caster", "safe", "safer"]):
            play_style = "ranged"
        elif any(
            term in text
            for term in ["melee", "close-range", "close range", "aggressive", "fast attack"]
        ):
            play_style = "melee"
        elif any(term in text for term in ["balanced", "versatile", "all around"]):
            play_style = "balanced"

        mobility = None
        if any(term in text for term in ["fast roll", "light", "mobile", "quick"]):
            mobility = "fast"
        elif any(term in text for term in ["tank", "tankier", "heavy", "poise"]):
            mobility = "tank"
        elif "mid roll" in text or "medium" in text:
            mobility = "medium"

        experience_level = None
        if any(term in text for term in ["new", "first playthrough", "beginner", "easy"]):
            experience_level = "new"
        elif any(term in text for term in ["experienced", "optimized", "min max", "pvp"]):
            experience_level = "experienced"

        return BuildPreferences(
            play_style=play_style,
            mobility=mobility,
            experience_level=experience_level,
            target_archetype=self.templates.first_mentioned_key(text) if len(mentioned) == 1 else None,
            considered_archetypes=sorted(mentioned),
        )

    def next_clarifying_question(self, pending_archetypes: list[str]) -> str:
        if {"dexterity", "sorcery"}.issubset(set(pending_archetypes)):
            return "Do you want the build to feel more close-range, ranged, or hybrid?"
        return "Do you prefer aggressive melee, safer ranged damage, or a balanced setup?"

    def _resolve_pending_archetype(
        self,
        preferences: BuildPreferences,
        state: ConversationState,
    ) -> str | None:
        pending = set(state.pending_archetypes)
        play_style = preferences.play_style or state.preferences.play_style
        if play_style == "ranged":
            return "sorcery" if not pending or "sorcery" in pending else None
        if play_style == "melee":
            if "dexterity" in pending:
                return "dexterity"
            if "strength" in pending:
                return "strength"
            return "quality" if not pending else None
        if play_style == "hybrid":
            return "pyromancy"
        if play_style == "balanced":
            return "quality"
        if preferences.target_archetype and (
            not pending or preferences.target_archetype in pending
        ):
            return preferences.target_archetype
        return None

    def _single_pending_archetype(self, state: ConversationState) -> str | None:
        if len(state.pending_archetypes) == 1:
            return state.pending_archetypes[0]
        return None

    def _looks_like_confirmation(self, text: str) -> bool:
        confirmation_terms = [
            "yes",
            "yeah",
            "yep",
            "sure",
            "sounds good",
            "do that",
            "lets do",
            "let's do",
            "go for it",
            "switch",
        ]
        return any(term in text for term in confirmation_terms)

    def _looks_like_switch_request(self, text: str) -> bool:
        question_leads = ["what", "how", "should", "is it", "would", "do you think"]
        if any(text.strip().startswith(lead) for lead in question_leads):
            return False

        switch_terms = [
            "i want",
            "make me",
            "build me",
            "give me",
            "switch to",
            "change to",
            "go with",
            "lets do",
            "let's do",
            "i will play",
            "ill play",
            "i'll play",
        ]
        return any(term in text for term in switch_terms)

    def _looks_like_exploration(self, text: str) -> bool:
        exploration_terms = [
            "what about",
            "what do you think",
            "opinion",
            "viable",
            "worth",
            "recommend",
            "should i",
            "how about",
            "is priest",
            "is faith",
            "is cleric",
        ]
        return any(term in text for term in exploration_terms)

    def _looks_like_build_request(self, text: str) -> bool:
        build_terms = [
            "build",
            "character",
            "class",
            "playstyle",
            "play style",
            "what should i play",
            "recommend me",
            "recommend a",
            "make me",
            "build me",
            "give me",
            "i want",
        ]
        return any(term in text for term in build_terms)

    def _looks_like_greeting(self, text: str) -> bool:
        normalized = text.strip().strip("!.?,")
        greetings = {"hi", "hello", "hey", "yo", "hola", "buenas", "thanks", "thank you"}
        return normalized in greetings

    def _looks_like_item_fact_question(self, text: str) -> bool:
        location_terms = [
            "where can i find",
            "where do i find",
            "where is",
            "how do i get",
            "how can i get",
            "where can i get",
            "drop location",
            "drops from",
            "farm",
            "location",
            "obtain",
        ]
        if any(term in text for term in location_terms):
            return True

        tokens = re.findall(r"[a-z0-9]+", text.lower())
        has_question_word = any(self._looks_like_word(token, ITEM_FACT_QUESTION_WORDS) for token in tokens)
        has_action_word = any(self._looks_like_word(token, ITEM_FACT_ACTION_WORDS) for token in tokens)
        has_item_noun = any(token in ITEM_FACT_NOUNS for token in tokens)
        if "build" in tokens and not has_action_word:
            return False
        return has_question_word and (has_action_word or has_item_noun)

    def _looks_like_word(self, token: str, choices: set[str]) -> bool:
        if token in choices:
            return True
        if len(token) < 3:
            return False
        return any(SequenceMatcher(None, token, choice).ratio() >= 0.78 for choice in choices)
