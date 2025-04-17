import { produce } from "immer";
import { applyActions } from "./actions";
import { sendEvent } from "./server-api";

type Handler = (args: RouteLitComponent[]) => void;

export class RouteLitManager {
  private listeners: Array<Handler> = [];
  private componentVersionListeners: Array<(v: number) => void> = [];
  componentStore: Map<string, React.ComponentType<any>> = new Map();
  private componentStoreVersion = 0;

  constructor(private componentsTree: RouteLitComponent[]) {}

  handleEvent = (e: CustomEvent<UIEventPayload>) => {
    sendEvent(e).then(this.applyActions, console.error);
  };

  applyActions = (actions: Action[]) => {
    const componentsTreeCopy = produce(this.componentsTree, (draft) => {
      applyActions(draft, actions);
    });
    this.componentsTree = componentsTreeCopy;
    this.notifyListeners();
  };

  initialize = () => {
    document.addEventListener("routelit:event", this.handleEvent as EventListener);
  };

  terminate = () => {
    document.removeEventListener(
      "routelit:event",
      this.handleEvent as EventListener
    );
  };

  registerComponent = (name: string, component: React.ComponentType<any>) => {
    this.componentStore.set(name, component);
    this.componentStoreVersion++;
    this.notifyListeners();
  };

  unregisterComponent = (name: string) => {
    this.componentStore.delete(name);
    this.componentStoreVersion++;
    this.notifyListeners();
  };

  getComponent = (name: string) => {
    return this.componentStore.get(name);
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
  
  getComponentStoreVersion = () => {
    return this.componentStoreVersion;
  };

  subscribeComponentStoreVersion = (listener: (v: number) => void): (() => void) => {
    this.componentVersionListeners.push(listener);
    return () => {
      this.componentVersionListeners = this.componentVersionListeners.filter((l) => l !== listener);
    };
  };

  forceUpdate = () => {
    this.componentStoreVersion++;
    for (const listener of this.componentVersionListeners) {
      listener(this.componentStoreVersion);
    }
  };
}
