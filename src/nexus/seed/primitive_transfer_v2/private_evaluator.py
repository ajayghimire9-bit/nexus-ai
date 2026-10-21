"""Private evaluator capability. Final task generation remains disabled.

No private outcome method is exposed by the transport. Keeping this explicitly
incomplete prevents running the old answer-bearing generator under a new label.
"""
from nexus.seed.open_primitive_transfer import ImmutableTrustedKernel


class PrivateEvaluator:
    def __init__(self):
        self.kernel = ImmutableTrustedKernel({
            "min_instructions": 1, "max_instructions": 64,
            "max_question_budget": 4, "max_execution_budget": 64,
            "max_admissible_complexity": 3,
        })

    def status(self):
        self.kernel.verify_integrity()
        return {"state": "UNAUTHORIZED_IMPLEMENTATION_INCOMPLETE",
                "fingerprint": self.kernel.kernel_signature()}
