import networkx as nx


class CausalGraph:
    """
    Directed acyclic graph for representing causal hypotheses.

    Edges represent proposed causal relationships.
    They do not automatically prove causation.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_variable(
        self,
        variable_id: str,
        description: str = "",
        category: str = "system",
    ) -> None:
        if not variable_id or not variable_id.strip():
            raise ValueError("Variable ID cannot be empty.")

        if variable_id in self.graph:
            raise ValueError(
                f"Variable '{variable_id}' already exists."
            )

        self.graph.add_node(
            variable_id,
            description=description,
            category=category,
        )

    def add_causal_link(
        self,
        cause: str,
        effect: str,
        confidence: float = 0.5,
        evidence_ids: list[str] | None = None,
        assumptions: list[str] | None = None,
        validated_by_simulator: bool = False,
    ) -> None:
        if cause not in self.graph:
            raise ValueError(f"Unknown cause variable: {cause}")

        if effect not in self.graph:
            raise ValueError(f"Unknown effect variable: {effect}")

        if cause == effect:
            raise ValueError("A variable cannot cause itself.")

        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0 and 1.")

        if self.graph.has_edge(cause, effect):
            raise ValueError(
                f"Causal link '{cause}' -> '{effect}' already exists."
            )

        self.graph.add_edge(
            cause,
            effect,
            confidence=confidence,
            evidence_ids=list(evidence_ids or []),
            assumptions=list(assumptions or []),
            validated_by_simulator=validated_by_simulator,
        )

        if not nx.is_directed_acyclic_graph(self.graph):
            self.graph.remove_edge(cause, effect)
            raise ValueError(
                "Causal link rejected: it would create a cycle."
            )

    def has_variable(self, variable_id: str) -> bool:
        return variable_id in self.graph

    def get_variables(self) -> list[dict]:
        return [
            {
                "variable_id": node,
                **attributes,
            }
            for node, attributes in sorted(
                self.graph.nodes(data=True)
            )
        ]

    def get_causal_links(self) -> list[dict]:
        return [
            {
                "cause": cause,
                "effect": effect,
                **attributes,
            }
            for cause, effect, attributes in sorted(
                self.graph.edges(data=True)
            )
        ]

    def get_possible_causes(
        self,
        variable_id: str,
    ) -> list[str]:
        if variable_id not in self.graph:
            raise ValueError(
                f"Unknown variable: {variable_id}"
            )

        return sorted(
            nx.ancestors(self.graph, variable_id)
        )

    def get_possible_effects(
        self,
        variable_id: str,
    ) -> list[str]:
        if variable_id not in self.graph:
            raise ValueError(
                f"Unknown variable: {variable_id}"
            )

        return sorted(
            nx.descendants(self.graph, variable_id)
        )

    def get_topological_order(self) -> list[str]:
        return list(nx.topological_sort(self.graph))

    def validate(self) -> dict:
        is_acyclic = nx.is_directed_acyclic_graph(
            self.graph
        )

        return {
            "valid": is_acyclic,
            "variable_count": self.graph.number_of_nodes(),
            "causal_link_count": self.graph.number_of_edges(),
            "is_acyclic": is_acyclic,
            "topological_order": (
                self.get_topological_order()
                if is_acyclic
                else []
            ),
        }

    def to_dict(self) -> dict:
        return {
            "variables": self.get_variables(),
            "causal_links": self.get_causal_links(),
            "validation": self.validate(),
        }