"""M5 resource manager.

Validates cumulative resource requirements against the V4 inventory.
All V4 resource quantities are synthetic prototype units.
"""

from typing import Any


def validate_resource_plan(
    resource_inventory: dict[str, Any],
    action_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check whether an ordered action plan fits available resources.

    Each action requirement must contain:
        {
            "action": "ACTION_NAME",
            "resources": {"power": 1, "operators": 1}
        }

    Requirements must be explicit numeric quantities.
    Qualitative labels such as "medium" are not converted automatically.
    """

    result = {
        "status": "UNKNOWN",
        "feasible": False,
        "checks": [],
        "total_consumption": {},
        "remaining_resources": {},
        "violations": [],
        "unknowns": [],
        "execution_authorized": False,
    }

    if not isinstance(resource_inventory, dict):
        result["unknowns"].append("Resource inventory must be a dictionary.")
        return result

    if not isinstance(action_requirements, list) or not action_requirements:
        result["unknowns"].append("Action requirements are missing or invalid.")
        return result

    availability = resource_inventory.get("current_availability")
    capacities = resource_inventory.get("capacities")

    if not isinstance(availability, dict):
        result["unknowns"].append("Current resource availability is missing.")
        return result

    if not isinstance(capacities, dict):
        result["unknowns"].append("Resource capacities are missing.")
        return result

    for resource, available in availability.items():
        capacity_data = capacities.get(resource)

        if not isinstance(capacity_data, dict):
            result["unknowns"].append(
                f"Capacity definition missing for {resource}."
            )
            continue

        capacity = capacity_data.get("capacity")

        if (
            isinstance(available, bool)
            or not isinstance(available, (int, float))
            or isinstance(capacity, bool)
            or not isinstance(capacity, (int, float))
            or available < 0
            or capacity < 0
            or available > capacity
        ):
            result["unknowns"].append(
                f"Invalid inventory values for {resource}."
            )
            continue

        result["remaining_resources"][resource] = available

    if result["unknowns"]:
        return result

    for item in action_requirements:
        if not isinstance(item, dict):
            result["unknowns"].append("Invalid action requirement entry.")
            continue

        action = item.get("action")
        resources = item.get("resources")

        if not isinstance(action, str) or not isinstance(resources, dict):
            result["unknowns"].append(
                "Each action needs a name and explicit resource dictionary."
            )
            continue

        for resource, required in resources.items():
            if (
                isinstance(required, bool)
                or not isinstance(required, (int, float))
                or required < 0
            ):
                result["unknowns"].append(
                    f"Invalid requirement for {action}: {resource}."
                )
                continue

            if resource not in result["remaining_resources"]:
                result["unknowns"].append(
                    f"Unknown resource: {resource}."
                )
                continue

            available_before = result["remaining_resources"][resource]

            check = {
                "action": action,
                "resource": resource,
                "required": required,
                "available_before": available_before,
            }

            if required > available_before:
                check["status"] = "FAIL"
                result["violations"].append(
                    f"{action} requires {required} {resource}, "
                    f"but only {available_before} is available."
                )
            else:
                check["status"] = "PASS"
                result["remaining_resources"][resource] -= required
                result["total_consumption"][resource] = (
                    result["total_consumption"].get(resource, 0) + required
                )

            result["checks"].append(check)

    if result["violations"]:
        result["status"] = "FAIL"
    elif result["unknowns"]:
        result["status"] = "UNKNOWN"
    else:
        result["status"] = "PASS"
        result["feasible"] = True

    return result
