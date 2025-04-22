import { produce } from "immer";
import { applyActions } from "./actions";
import { sendEvent } from "./server-api";
type Handler = (args: RouteLitComponent[]) => void;

export class RouteLitManager {
  private listeners: Array<Handler> = [];

  constructor(
    private componentsTree: RouteLitComponent[],
    private fragmentId?: string
  ) {}

  handleEvent = (e: CustomEvent<UIEventPayload>) => {
    if (e.detail.type === "navigate" && this.fragmentId)
      // Let the upper manager handle the navigation
      return;
    sendEvent(e, this.fragmentId).then(this.applyActions, console.error);
    e.stopPropagation();
  };

  applyActions = (actions: Action[]) => {
    const componentsTreeCopy = produce(this.componentsTree, (draft) => {
      applyActions(draft, actions);
    });
    this.componentsTree = componentsTreeCopy;
    this.notifyListeners();
  };

  initialize = () => {
    document.addEventListener(
      "routelit:event",
      this.handleEvent as EventListener
    );
    window.addEventListener("popstate", this.handlePopState as EventListener);
  };

  handlePopState = () => {
    const currentUrl = window.location.href;
    const navigateEvent = new CustomEvent<NavigateEventPayload>(
      "routelit:event",
      {
        detail: {
          type: "navigate",
          id: "browser-navigation",
          href: currentUrl,
        },
      }
    );
    document.dispatchEvent(navigateEvent);
  };

  terminate = () => {
    document.removeEventListener(
      "routelit:event",
      this.handleEvent as EventListener
    );
    window.removeEventListener(
      "popstate",
      this.handlePopState as EventListener
    );
  };

  getComponentsTree = (): RouteLitComponent[] => {
    return this.componentsTree;
  };

  subscribe = (listener: Handler): (() => void) => {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  };

  private notifyListeners = () => {
    for (const listener of this.listeners) {
      listener(this.componentsTree);
    }
  };
}
