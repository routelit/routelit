from typing import List, Literal, Optional, Union

from ..domain import (
    Action,
    AddAction,
    RemoveAction,
    RouteLitElement,
    SessionKeys,
    UpdateAction,
    ViewFn,
)


def compare_elements(
    a: List[RouteLitElement],
    b: List[RouteLitElement],
    target: Literal["app", "fragment"],
    address: Optional[List[int]] = None,
) -> List[Action]:
    """
    Compare two lists of elements and return a list of actions to transform the first list into the second.
    Uses a key-based approach to create minimal operations that preserve element identity.
    Handles insertions by pushing subsequent elements down rather than removing and re-adding them.
    """
    if address is None:
        address = []

    actions: List[Action] = []

    # Maps to track elements by key
    a_map = {elem.key: (i, elem) for i, elem in enumerate(a)}
    b_map = {elem.key: (i, elem) for i, elem in enumerate(b)}

    # Elements present only in a (to be removed)
    keys_to_remove = set(a_map.keys()) - set(b_map.keys())

    # Elements present only in b (to be added)
    keys_to_add = set(b_map.keys()) - set(a_map.keys())

    # Elements present in both lists
    common_keys = set(a_map.keys()) & set(b_map.keys())

    # Build a simulation of the list transformation
    # Start with list a's keys
    current_state = [elem.key for elem in a]

    # Step 1: Process removals from right to left to avoid index shifts
    for key in sorted(keys_to_remove, key=lambda k: -a_map[k][0]):
        idx = current_state.index(key)
        actions.append(RemoveAction(address=[*address, idx], key=key, target=target))
        current_state.pop(idx)

    # Step 2: Process position changes and additions
    # Sort by target position in b to ensure correct ordering
    keys_to_process = sorted(
        common_keys.union(keys_to_add),
        key=lambda k: b_map.get(k, (float("inf"), None))[0],
    )

    for key in keys_to_process:
        target_idx = b_map[key][0]  # Where this element should be in the final list

        if key in common_keys:
            # Element exists in both lists - check if it moved
            current_idx = current_state.index(key)

            # Calculate the correct target index in current_state
            expected_idx = min(target_idx, len(current_state))

            # Adjust expected_idx based on elements that come before this one in b
            # but aren't yet in current_state
            adjustment = 0
            for preceding_key in [b[i].key for i in range(target_idx)]:
                if preceding_key not in current_state and preceding_key in b_map:
                    adjustment -= 1

            expected_idx += adjustment
            expected_idx = max(0, expected_idx)  # Ensure index is not negative

            if current_idx != expected_idx:
                # The element is in the wrong position and needs to move
                # Remove it from current position and insert at expected position
                current_state.pop(current_idx)
                current_state.insert(expected_idx, key)

                # Update props if needed
                old_elem = a_map[key][1]
                new_elem = b_map[key][1]

                if old_elem.props != new_elem.props:
                    # Element moved AND props changed - remove and add
                    actions.append(RemoveAction(address=[*address, current_idx], key=key, target=target))
                    actions.append(
                        AddAction(address=[*address, expected_idx], element=new_elem, key=key, target=target)
                    )
                else:
                    # Element moved but props unchanged - we could optimize with a special move action
                    # For now, simulate with remove and add
                    actions.append(RemoveAction(address=[*address, current_idx], key=key, target=target))
                    actions.append(
                        AddAction(address=[*address, expected_idx], element=new_elem, key=key, target=target)
                    )
            else:
                # Position is correct, check if props need updating
                old_elem = a_map[key][1]
                new_elem = b_map[key][1]

                if old_elem.props != new_elem.props:
                    actions.append(
                        UpdateAction(
                            address=[*address, current_idx],
                            props=new_elem.props,
                            key=key,
                            target=target,
                        )
                    )
        else:
            # This is a new element (only in b)
            # Determine insertion point based on previous elements
            if target_idx == 0:
                insert_at = 0
            else:
                # Find the element that should come before this one
                prev_key_in_b = b[target_idx - 1].key

                if prev_key_in_b in current_state:
                    # If previous element exists in current state, insert after it
                    insert_at = current_state.index(prev_key_in_b) + 1
                else:
                    # Find closest preceding element that exists in current state
                    insert_at = 0
                    for i in range(target_idx - 1, -1, -1):
                        if b[i].key in current_state:
                            insert_at = current_state.index(b[i].key) + 1
                            break

            # Add the new element
            new_elem = b_map[key][1]
            actions.append(AddAction(address=[*address, insert_at], element=new_elem, key=key, target=target))
            current_state.insert(insert_at, key)

    # Step 3: Process children recursively
    for key in common_keys:
        if key in current_state:  # Skip if element was removed due to position change
            current_idx = current_state.index(key)
            old_idx = a_map[key][0]
            new_idx = b_map[key][0]

            # Only process children if we didn't already handle this element with remove/add
            if not any(isinstance(action, RemoveAction) and action.key == key for action in actions):
                # Recursively compare children
                old_children = a[old_idx].children or []
                new_children = b[new_idx].children or []

                child_actions = compare_elements(
                    old_children, new_children, target=target, address=[*address, current_idx]
                )
                actions.extend(child_actions)

    return actions


def get_elements_at_address(elements: List[RouteLitElement], address: List[int]) -> List[RouteLitElement]:
    _elements = elements
    for idx in address:
        if idx < 0 or idx >= len(_elements):
            # If the address is invalid, return an empty list
            # This can happen when the UI structure has changed and the stored address is no longer valid
            return []
        children = _elements[idx].children
        if children is None:
            raise ValueError(f"Element at index {idx} has no children")
        _elements = children
    return _elements


def set_elements_at_address(
    elements: List[RouteLitElement], address: List[int], value: List[RouteLitElement]
) -> List[RouteLitElement]:
    new_elements = elements.copy()
    el_or_els: Union[List[RouteLitElement], RouteLitElement] = new_elements
    for idx in address:
        if isinstance(el_or_els, list):
            if idx < 0 or idx >= len(el_or_els):
                # If the address is invalid, return the original elements unchanged
                # This can happen when the UI structure has changed and the stored address is no longer valid
                return elements
            el_or_els = el_or_els[idx]
        elif isinstance(el_or_els, RouteLitElement) and el_or_els.children is not None:
            if idx < 0 or idx >= len(el_or_els.children):
                # If the address is invalid, return the original elements unchanged
                return elements
            el_or_els = el_or_els.children[idx]
        else:
            raise ValueError(f"Cannot set object at address {address} from object of type {type(elements)}")

    # At this point, el_or_els should be a RouteLitElement
    if not isinstance(el_or_els, RouteLitElement):
        raise TypeError(f"Expected RouteLitElement at address {address}, got {type(el_or_els)}")

    el_or_els.children = value
    return new_elements


def build_view_task_key(view_fn: ViewFn, fragment_id: Optional[str], session_keys: SessionKeys) -> str:
    return f"{session_keys.view_tasks_key}-{view_fn.__name__}#{fragment_id or 'app'}"
