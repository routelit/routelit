
interface RouteLitComponent {
    key: string;
    name: string;
    props: Record<string, any>;
    children?: RouteLitComponent[];
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
    props: Record<string, any>;
}

interface UIEventPayload {
    type: string;
    id: string;
    [key: string]: any;
}

interface NavigateEventPayload extends UIEventPayload {
    type: "navigate";
    href: string;
    isExternal?: boolean;
    replace?: boolean;
    target?: "_blank" | "_self";
}

interface ChangeEventPayload extends UIEventPayload {
    value: string|number;
}

