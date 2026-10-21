"""Neural grounding layer for the NEXUS Seed master architecture.

Converts raw text, vision, audio/speech, environment sensors, and code inputs
into structured GroundedObservation instances. Includes:
- Compact byte/subword tokenizer
- 128-dimensional embeddings + 2-layer bidirectional GRU (~1.5M parameters)
  with separate intent, concept, skill, argument, and confidence heads
- Deterministic symbolic/hybrid grounding rules so exact structured extraction
  works reliably even before large-scale supervised pretraining
- Modality encoder adapters for vision, audio/speech, sensors, and code tokens
"""
import hashlib
import json
import re
from typing import Any
from .types import GroundedObservation

INTENTS = (
    "execute_skill",
    "teach_concept",
    "teach_skill",
    "query_relation",
    "query_constraint",
    "query_math",
    "query_causal",
    "query_analogy",
    "plan_action",
    "code_task",
    "investigate",
    "greeting",
    "inspect_memory",
)

KNOWN_SKILLS = (
    "sorting",
    "reverse",
    "unique",
    "even",
    "increment",
    "move",
    "filter",
    "sum",
)

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "in", "on",
    "for", "from", "with", "by", "at", "as", "into", "if", "and", "or", "then",
    "could", "would", "can", "you", "please", "these", "those", "this", "that",
    "what", "where", "when", "why", "how", "who", "which", "means", "mean",
    "arrange", "order", "smallest", "largest", "relative", "hello", "hi", "hey",
    "nexus", "do", "does", "did", "it", "them", "list", "sequence", "number",
    "numbers", "object", "objects",
}


class CompactSubwordTokenizer:
    """Byte + frequent subword tokenizer with bounded vocabulary."""

    BASE_SUBWORDS = (
        "<pad>", "<bos>", "<eos>", "<unk>",
        "arrange", "smallest", "largest", "sort", "sorting", "reverse", "flip",
        "order", "sequence", "north", "south", "east", "west", "older", "younger",
        "taller", "shorter", "causes", "correlates", "explain", "move", "code",
        "function", "debug", "repair", "test", "means", "bright", "red", "blue",
        "green", "yellow", "circle", "square", "triangle", "small", "large",
        "ascending", "descending",
    )

    def __init__(self, vocab_size: int = 4096):
        if type(vocab_size) is not int or not 512 <= vocab_size <= 16384:
            raise ValueError("invalid_vocab_size")
        self.vocab_size = vocab_size
        self.subword_to_id = {w: i for i, w in enumerate(self.BASE_SUBWORDS)}
        self.byte_offset = len(self.BASE_SUBWORDS)

    def encode(self, text: str, max_length: int = 128) -> list[int]:
        if type(text) is not str:
            raise ValueError("tokenizer_text_required")
        tokens = [1]  # <bos>
        words = re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", text.lower())
        for word in words:
            if word in self.subword_to_id:
                tokens.append(self.subword_to_id[word])
            else:
                for b in word.encode("utf-8")[:16]:
                    tokens.append(min(self.vocab_size - 1, self.byte_offset + b))
            if len(tokens) >= max_length - 1:
                break
        tokens.append(2)  # <eos>
        return tokens[:max_length]


def build_torch_grounding_encoder(
    vocab_size: int = 4096,
    embed_dim: int = 128,
    hidden_dim: int = 224,
    num_intents: int = len(INTENTS),
    num_concepts: int = 64,
    num_skills: int = len(KNOWN_SKILLS),
    num_arguments: int = 32,
):
    """Construct the recommended 128-D, 2-layer BiGRU encoder (~1.5M parameters) with 5 heads."""
    import torch
    import torch.nn as nn

    class GroundingBiGRUEncoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.vocab_size = vocab_size
            self.embed_dim = embed_dim
            self.hidden_dim = hidden_dim
            self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
            self.encoder = nn.GRU(
                input_size=embed_dim,
                hidden_size=hidden_dim,
                num_layers=2,
                batch_first=True,
                bidirectional=True,
            )
            feat_dim = hidden_dim * 2
            self.intent_head = nn.Linear(feat_dim, num_intents)
            self.concept_head = nn.Linear(feat_dim, num_concepts)
            self.skill_head = nn.Linear(feat_dim, num_skills)
            self.argument_head = nn.Linear(feat_dim, num_arguments)
            self.confidence_head = nn.Sequential(nn.Linear(feat_dim, 1), nn.Sigmoid())
            self.forward_calls = 0

        def parameter_count(self) -> int:
            return sum(p.numel() for p in self.parameters())

        def forward(self, token_ids):
            self.forward_calls += 1
            emb = self.embedding(token_ids)
            seq_out, _ = self.encoder(emb)
            pooled = seq_out.mean(dim=1)
            return dict(
                pooled_embedding=pooled,
                intent_logits=self.intent_head(pooled),
                concept_logits=self.concept_head(pooled),
                skill_logits=self.skill_head(pooled),
                argument_logits=self.argument_head(pooled),
                confidence=self.confidence_head(pooled).squeeze(-1),
            )

    model = GroundingBiGRUEncoder()
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model


class NeuralGroundingLayer:
    """Language and multimodal grounding layer producing typed GroundedObservation objects."""

    def __init__(self, known_concepts: set[str] | None = None, Known_skills: set[str] | None = None, enable_torch_model: bool = False):
        self.tokenizer = CompactSubwordTokenizer(vocab_size=4096)
        self.known_concepts = set(known_concepts or {
            "red", "blue", "green", "yellow", "bright", "circle", "square", "triangle",
            "small", "large", "ascending", "descending", "north", "south", "east", "west",
            "older", "younger", "taller", "shorter",
        })
        self.known_skills = set(Known_skills or KNOWN_SKILLS)
        self.torch_model = build_torch_grounding_encoder() if enable_torch_model else None
        self.embedding_cache: dict[str, list[float]] = {}

    def register_concept(self, name: str):
        self.known_concepts.add(name.lower().strip())

    def register_skill(self, name: str):
        self.known_skills.add(name.lower().strip())

    def embed_text(self, text: str) -> list[float]:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
        if key in self.embedding_cache:
            return list(self.embedding_cache[key])
        token_ids = self.tokenizer.encode(text)
        if self.torch_model is not None:
            import torch
            with torch.no_grad():
                out = self.torch_model(torch.tensor([token_ids], dtype=torch.long))
                vec = [round(float(v), 6) for v in out["pooled_embedding"][0, :128].tolist()]
        else:
            # Deterministic 128-D projection when running on tier-1 stdlib core
            digest_bytes = hashlib.sha512(json.dumps(token_ids).encode("utf-8")).digest() * 2
            vec = [round((b - 128.0) / 128.0, 6) for b in digest_bytes[:128]]
        if len(self.embedding_cache) < 512:
            self.embedding_cache[key] = vec
        return list(vec)

    def ground_text(self, text: str, known_concepts: set[str] | None = None, known_skills: set[str] | None = None) -> GroundedObservation:
        if type(text) is not str or not text.strip() or len(text) > 5000:
            raise ValueError("valid_grounding_text_required")
        raw = text.strip()
        lower = re.sub(r"\s+", " ", raw.lower()).strip()
        concepts_pool = self.known_concepts | set(known_concepts or ())
        skills_pool = self.known_skills | set(known_skills or ())

        token_ids = self.tokenizer.encode(raw)
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*", lower)
        quantities = []
        for match in re.finditer(r"(?<![a-zA-Z0-9_])-?\d+(?:\.\d+)?", raw):
            val_str = match.group(0)
            quantities.append(float(val_str) if "." in val_str else int(val_str))

        json_lists = []
        for match in re.finditer(r"\[[^\[\]]*\]", raw):
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    json_lists.append(parsed)
            except ValueError:
                pass

        recognized_concepts = sorted({w for w in words if w in concepts_pool})
        new_vocabulary = []
        for w in words:
            if w not in STOPWORDS and w not in concepts_pool and w not in skills_pool and len(w) > 1 and not re.fullmatch(r"o\d+", w):
                if w not in new_vocabulary:
                    new_vocabulary.append(w)

        intent = "general_query"
        skill = None
        arguments: Any = {}
        constraint = None
        confidence = 0.82
        ambiguity = False
        entities = []
        relations = []
        requested_goal: Any = None

        # Check specific structured patterns
        # 1. Sorting / arranging pattern (exact example from specification)
        if ("arrange" in lower or "sort" in lower or "order" in lower) and (
            "smallest to largest" in lower or "ascending" in lower or "largest to smallest" in lower or "descending" in lower
        ):
            intent = "execute_skill"
            skill = "sorting"
            constraint = "descending" if ("largest to smallest" in lower or "descending" in lower) else "ascending"
            arguments = json_lists[0] if json_lists else "supplied_list"
            confidence = 0.94
            ambiguity = not bool(json_lists)
            requested_goal = dict(
                intent=intent,
                skill=skill,
                arguments=arguments,
                constraint=constraint,
                confidence=confidence,
            )

        # 2. Concept or skill teaching pattern: '"Flip" means reverse the order of a sequence' or '"Scarlet" means bright red'
        elif re.search(r'["“]?([a-zA-Z][a-zA-Z0-9_]*)["”]?\s+(?:means|is defined as)\s+(.+)', raw, flags=re.I):
            m = re.search(r'["“]?([a-zA-Z][a-zA-Z0-9_]*)["”]?\s+(?:means|is defined as)\s+(.+)', raw, flags=re.I)
            term = m.group(1).lower()
            definition_text = m.group(2).strip().rstrip(".!?")
            def_lower = definition_text.lower()
            if term not in new_vocabulary and term not in concepts_pool:
                new_vocabulary.insert(0, term)
            linked_skill = None
            if "reverse" in def_lower and ("order" in def_lower or "sequence" in def_lower or "list" in def_lower):
                linked_skill = "reverse"
                intent = "teach_concept"
            elif "sort" in def_lower or "smallest to largest" in def_lower:
                linked_skill = "sorting"
                intent = "teach_concept"
            else:
                intent = "teach_concept"
            skill = linked_skill
            arguments = dict(term=term, definition=definition_text, linked_skill=linked_skill)
            confidence = 0.93
            requested_goal = dict(
                intent=intent,
                term=term,
                definition=definition_text,
                linked_skill=linked_skill,
                confidence=confidence,
            )

        # 3. Relational query pattern: "If A is north of B and B is north of C, where is A relative to C?"
        elif re.search(r"if\s+([a-zA-Z0-9_]+)\s+is\s+([a-z ]+?)\s+(?:of|than)\s+([a-zA-Z0-9_]+)\s+and\s+([a-zA-Z0-9_]+)\s+is\s+([a-z ]+?)\s+(?:of|than)\s+([a-zA-Z0-9_]+)", raw, flags=re.I):
            m = re.search(
                r"if\s+([a-zA-Z0-9_]+)\s+is\s+([a-z ]+?)\s+(?:of|than)\s+([a-zA-Z0-9_]+)\s+and\s+([a-zA-Z0-9_]+)\s+is\s+([a-z ]+?)\s+(?:of|than)\s+([a-zA-Z0-9_]+)",
                raw,
                flags=re.I,
            )
            e1, rel1, e2, e3, rel2, e4 = (
                m.group(1),
                m.group(2).strip().lower(),
                m.group(3),
                m.group(4),
                m.group(5).strip().lower(),
                m.group(6),
            )
            entities = [e1, e2, e3, e4]
            unique_entities = []
            for e in entities:
                if e not in unique_entities:
                    unique_entities.append(e)
            entities = unique_entities
            relations = [
                dict(relation=rel1, subject=e1, object=e2),
                dict(relation=rel2, subject=e3, object=e4),
            ]
            q_match = re.search(r"where\s+is\s+([a-zA-Z0-9_]+)\s+relative\s+to\s+([a-zA-Z0-9_]+)", raw, flags=re.I)
            if not q_match:
                q_match = re.search(r"is\s+([a-zA-Z0-9_]+)\s+[a-z ]+\s+(?:of|than)\s+([a-zA-Z0-9_]+)", raw.split(",")[-1], flags=re.I)
            query_pair = (q_match.group(1), q_match.group(2)) if q_match else (e1, e4)
            intent = "query_relation"
            arguments = dict(relations=relations, query_subject=query_pair[0], query_object=query_pair[1])
            confidence = 0.96
            requested_goal = dict(
                intent=intent,
                query_subject=query_pair[0],
                query_object=query_pair[1],
                relation=rel1,
                confidence=confidence,
            )

        # 4. Greeting & natural conversational check-ins
        elif lower.rstrip(".!?") in (
            "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
            "hello nexus", "hi nexus", "hey nexus",
        ):
            intent = "greeting"
            confidence = 0.99
            requested_goal = dict(intent="greeting", subtype="hello", confidence=confidence)

        elif any(p in lower for p in (
            "how are you", "how are u", "how r u", "how is it going", "how's it going",
            "how do you feel", "are you there", "you good",
        )):
            intent = "greeting"
            arguments = dict(subtype="status_check")
            confidence = 0.98
            requested_goal = dict(intent="greeting", subtype="status_check", confidence=confidence)

        elif any(p in lower for p in (
            "who are you", "what are you", "what is your name", "tell me about yourself",
            "introduce yourself",
        )):
            intent = "greeting"
            arguments = dict(subtype="identity")
            confidence = 0.98
            requested_goal = dict(intent="greeting", subtype="identity", confidence=confidence)

        elif lower.rstrip(".!?") in ("thanks", "thank you", "thx", "ty", "good job", "great job", "awesome", "nice", "cool", "well done"):
            intent = "greeting"
            arguments = dict(subtype="appreciation")
            confidence = 0.99
            requested_goal = dict(intent="greeting", subtype="appreciation", confidence=confidence)

        elif any(p in lower for p in (
            "learning to learn", "meta learning", "meta-learning", "general intelligence",
            "are you agi", "did we achieve", "run general suite",
        )):
            intent = "meta_learning_benchmark"
            confidence = 0.96
            requested_goal = dict(intent="meta_learning_benchmark", text=raw, confidence=confidence)

        # 5. Causal reasoning query
        elif any(phrase in lower for phrase in ("causes", "correlates with", "confounder", "causal", "explain both")):
            intent = "query_causal"
            confidence = 0.88
            requested_goal = dict(intent=intent, text=raw, confidence=confidence)

        # 6. Analogical reasoning query
        elif "analogous" in lower or "analogy" in lower or ("like" in lower and "reverse" in lower and "movement" in lower):
            intent = "query_analogy"
            confidence = 0.89
            requested_goal = dict(intent=intent, text=raw, confidence=confidence)

        # 7. Mathematical / equation / arithmetic query
        elif any(k in lower for k in ("solve", "calculate", "equation", "compute")) or re.search(r"\d+\s*[\+\-\*\/=]\s*\d+", lower):
            intent = "query_math"
            confidence = 0.91
            requested_goal = dict(intent=intent, expression=raw, confidence=confidence)

        # 8. Constraint satisfaction query
        elif any(k in lower for k in ("schedule", "constraint", "assign", "satisfy", "Ordering puzzle")):
            intent = "query_constraint"
            confidence = 0.87
            requested_goal = dict(intent=intent, text=raw, confidence=confidence)

        # 9. Coding / debugging request
        elif any(k in lower for k in ("write code", "synthesize", "debug", "fix bug", "function", "def ")):
            intent = "code_task"
            confidence = 0.90
            requested_goal = dict(intent=intent, specification=raw, confidence=confidence)

        # 10. Skill execution with explicit list
        elif json_lists and any(s in lower for s in skills_pool):
            matched_skill = next(s for s in sorted(skills_pool) if s in lower)
            intent = "execute_skill"
            skill = matched_skill
            arguments = json_lists[0]
            confidence = 0.92
            requested_goal = dict(intent=intent, skill=skill, arguments=arguments, confidence=confidence)

        # 11. World movement / planning
        elif lower.startswith("move "):
            intent = "plan_action"
            skill = "move"
            confidence = 0.90
            for obj_id in re.findall(r"\bo[1-9]\b", lower):
                if obj_id not in entities:
                    entities.append(obj_id)
            ambiguity = len(entities) == 0 and any(p in lower for p in ("it", "that", "object"))
            requested_goal = dict(intent=intent, command=raw, entities=entities, confidence=confidence)

        return GroundedObservation(
            concepts=recognized_concepts,
            entities=entities,
            relations=relations,
            quantities=quantities,
            requested_goal=requested_goal,
            uncertainty=dict(
                confidence=round(confidence, 4),
                ambiguous=ambiguity,
                new_vocabulary=new_vocabulary,
            ),
            provenance=dict(
                modality="language",
                tokenizer_vocab_size=self.tokenizer.vocab_size,
                token_count=len(token_ids),
                embedding_dim=128,
                intent=intent,
                skill=skill,
                arguments=arguments,
                constraint=constraint,
                torch_encoder_active=self.torch_model is not None,
            ),
        )

    def ground_vision(self, scene_objects: list[dict]) -> GroundedObservation:
        """Compact vision/scene encoder producing the same GroundedObservation type."""
        if type(scene_objects) is not list:
            raise ValueError("vision_scene_objects_list_required")
        concepts = set()
        entities = []
        relations = []
        quantities = [len(scene_objects)]
        for obj in scene_objects:
            if type(obj) is not dict:
                continue
            obj_id = str(obj.get("id", f"obj_{len(entities)}"))
            entities.append(obj_id)
            for key in ("color", "shape", "size"):
                if key in obj and isinstance(obj[key], str):
                    concepts.add(obj[key].lower())
        for i, a in enumerate(scene_objects):
            for b in scene_objects[i + 1:]:
                if isinstance(a, dict) and isinstance(b, dict) and "x" in a and "y" in a and "x" in b and "y" in b:
                    if a["y"] < b["y"]:
                        relations.append(dict(relation="north", subject=a.get("id"), object=b.get("id")))
                    elif a["y"] > b["y"]:
                        relations.append(dict(relation="south", subject=a.get("id"), object=b.get("id")))
                    if a["x"] < b["x"]:
                        relations.append(dict(relation="west", subject=a.get("id"), object=b.get("id")))
                    elif a["x"] > b["x"]:
                        relations.append(dict(relation="east", subject=a.get("id"), object=b.get("id")))
        return GroundedObservation(
            concepts=sorted(concepts),
            entities=entities,
            relations=relations[:32],
            quantities=quantities,
            requested_goal=None,
            uncertainty=dict(confidence=0.98, ambiguous=False),
            provenance=dict(modality="vision", object_count=len(scene_objects)),
        )

    def ground_audio(self, transcript: str, acoustic_confidence: float = 0.9) -> GroundedObservation:
        """Audio/speech encoder adapter that wraps transcript grounding with acoustic uncertainty."""
        obs = self.ground_text(transcript)
        combined_conf = round(float(obs.uncertainty.get("confidence", 0.8)) * float(acoustic_confidence), 4)
        obs.uncertainty["confidence"] = combined_conf
        obs.uncertainty["acoustic_confidence"] = float(acoustic_confidence)
        obs.provenance["modality"] = "audio_speech"
        return obs.validate()

    def ground_sensor(self, readings: dict) -> GroundedObservation:
        """Sensor and environment encoder producing typed GroundedObservation."""
        if type(readings) is not dict:
            raise ValueError("sensor_readings_dict_required")
        quantities = [v for v in readings.values() if type(v) in (int, float) and not isinstance(v, bool)]
        entities = sorted(str(k) for k in readings.keys())
        return GroundedObservation(
            concepts=["sensor_reading"],
            entities=entities,
            relations=[],
            quantities=quantities,
            requested_goal=readings.get("goal"),
            uncertainty=dict(confidence=0.95, ambiguous=False),
            provenance=dict(modality="sensor_environment", keys=entities),
        )

    def ground_code(self, source_code: str) -> GroundedObservation:
        """Code-specific token encoder extracting symbols, functions, and structural relations."""
        if type(source_code) is not str:
            raise ValueError("code_string_required")
        funcs = re.findall(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", source_code)
        classes = re.findall(r"class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[\(:]", source_code)
        imports = re.findall(r"(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_\.]*)", source_code)
        relations = [dict(relation="defines_function", subject="module", object=f) for f in funcs]
        relations += [dict(relation="imports", subject="module", object=imp) for imp in imports]
        return GroundedObservation(
            concepts=["python_code"] + (["function_definition"] if funcs else []),
            entities=funcs + classes,
            relations=relations[:64],
            quantities=[len(source_code.splitlines())],
            requested_goal=dict(intent="code_task", functions=funcs),
            uncertainty=dict(confidence=0.97, ambiguous=False),
            provenance=dict(modality="code", line_count=len(source_code.splitlines()), imports=imports),
        )
