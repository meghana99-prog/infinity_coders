# CHRONOS-X — Responsibility 05: Stochastic Simulation Engine

This package implements Stage 5 using the team's **shared Universal Dataset V4**. The V4 dataset and original V3 baseline are included unchanged. Do not create a separate Stage 5 dataset.

## What it does

- Reads Stage 5 inputs through the V4 responsibility contract: `state_history`, `action_models`, `resource_inventory`, and `simulation_config`.
- Builds candidate action sequences (monitor-only, individual interventions, and ordered two-action combinations).
- Runs reproducible Monte Carlo simulations (10,000 iterations by default; seed 42).
- Models per-step thermal drift, stochastic action effects, delayed effects, action failure, action duration, action costs, and synthetic resource-token consumption.
- Applies action preconditions and structured safety rules independently before scheduling actions. Rejected actions cannot be rescued by a better simulation score.
- Reports mean/P95 temperature, temperature-threshold exceedance rate, failure rate, resource usage, costs, and mean/P05/P95 temperature trajectories.
- Supports all V4 scenario variants and abstains on the pressure-instability variant because pressure dynamics are not provided.
- Applies a separate incident-relevance gate: in `COOLING_FAILURE`, network isolation is not treated as a cooling mitigation; if backup cooling is unavailable and shutdown is unauthorized, Stage 5 abstains with an explicit reason.
- Never authorizes equipment control. The output is for simulation review and must pass Responsibility 06 independent safety verification.

## Important dataset limitations (preserved, not silently filled)

1. Temperature unit is unspecified.
2. The value 95 is only the V3 restriction that disallows monitoring-only when temperature is above 95. It is **not** a validated catastrophe threshold.
3. Pressure has no unit, threshold, or dynamics; this engine does not simulate pressure.
4. Action effect distributions are synthetic illustrative parameters, not validated equipment performance.
5. V4 resource capacities are synthetic tokens. Where V4 uses qualitative labels (`medium`, `required`), this code maps them to token counts as an explicitly labelled modelling assumption.
6. Plans are scheduled sequentially, even if an action says it could run in parallel. This avoids assuming concurrency that has not been fully specified.
7. `best_candidate_for_human_review` is a simulation ranking only. `recommended_plan` remains `null`, `execution_authorized` remains `false`, and independent safety review is required.

## Windows PowerShell setup

Run these commands from the team repository root:

```powershell
python -m pytest backend/tests/test_m5_stochastic_simulation.py -v
python -m pytest backend/tests -v
```

The first command runs Stage 5 tests. The second runs the complete backend test suite.
## Output contract

`candidate_plans` contains ranked simulation results and per-plan safety checks. `best_candidate_for_human_review` is the top feasible candidate under the transparent ranking (threshold exceedance rate, P95 maximum temperature, then mean action cost). `abstain` is true when no technically feasible and incident-relevant candidate exists, or the pressure-instability scenario prevents a whole-system recommendation. `abstention_reason` explains the reason. A technically feasible but unrelated action may remain in `candidate_plans` for audit, but it cannot become the best candidate. This ranking is not a risk-acceptance policy.

## Architecture boundary

Stage 5 proposes and compares simulated plans. Stage 6 is the independent safety veto. Stage 5 must not issue commands to real equipment or override Stage 6.



