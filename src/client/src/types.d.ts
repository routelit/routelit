
interface RouteLitComponent {
    key: string;
    /**
     * The name or type of the component. It could be a html tag name or a custom component name.
     */
    name: string;
    props: Record<string, unknown>;
    children?: RouteLitComponent[];
    address?: number[];
}

type ActionType = "add" | "remove" | "update";

interface Action {
    type: string;
    /**
     * The address is the sequence of indices to the array tree of elements in the session state
     * from the root to the target element.
     */
    address: number[];
}

interface AddAction extends Action {
    type: "add";
    element: RouteLitComponent;
}

interface RemoveAction extends Action {
    type: "remove";
}

interface UpdateAction extends Action {
    type: "update";
    props: Record<string, unknown>;
}

interface ActionsResponse {
    actions: Action[];
    target: "app" | "fragment";
}

interface UIEventPayload {
    type: string;
    id: string;
    formId?: string;
    [key: string]: unknown;
}

interface NavigateEventPayload extends UIEventPayload {
    type: "navigate";
    href: string;
    lastURL?: string;
    isExternal?: boolean;
    replace?: boolean;
    target?: "_blank" | "_self";
}

interface ChangeEventPayload extends UIEventPayload {
    value: string|number;
}
