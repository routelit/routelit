import { produce } from "immer";
import { applyActions, prependAddressToActions } from "./actions";
import { sendEvent } from "./server-api";

type Handler = (args: RouteLitComponent[]) => void;
type IsLoadingHandler = (args: boolean) => void;
type ErrorHandler = (args: Error) => void;

interface RouteLitManagerProps {
  componentsTree?: RouteLitComponent[];
  fragmentId?: string;
  parentManager?: RouteLitManager;
  address?: number[];
}

export class RouteLitManager {
  private listeners: Array<Handler> = [];
  private isLoadingListeners: Array<IsLoadingHandler> = [];
  private errorListeners: Array<ErrorHandler> = [];
  private componentsTree?: RouteLitComponent[];
  private _isLoading: boolean = false;
  private _error?: Error;
  private fragmentId?: string;
  private parentManager?: RouteLitManager;
  private address?: number[];
  private lastURL?: string;

  constructor(props: RouteLitManagerProps) {
    this.componentsTree = props.componentsTree;
    this.fragmentId = props.fragmentId;
    this.parentManager = props.parentManager;
    this.address = props.address;
    this.lastURL = props.parentManager?.getLastURL() ?? window.location.href;
  }

  getLastURL = (): string => {
    return this.parentManager?.getLastURL() ?? this.lastURL!;
  };

  handleEvent = (e: CustomEvent<UIEventPayload>) => {
    if (e.detail.type === "navigate" && this.fragmentId)
      // Let the upper manager handle the navigation
      return;
    if (e.detail.type === "navigate")
      this.lastURL = e.detail.href.startsWith("http")
        ? e.detail.href
        : window.location.origin + e.detail.href;
    this._error = undefined;
    this._isLoading = true;
    this.notifyIsLoading();
    sendEvent(e, this.fragmentId)
      .then(this.applyActions, this.handleError)
      .finally(() => {
        this._isLoading = false;
        this.notifyIsLoading();
      });
    e.stopPropagation();
  };

  handleError = (e: Error) => {
    this._error = e;
    this.notifyError();
  };

  applyActions = (actionsResp: ActionsResponse, shouldNotify = true) => {
    if (this.fragmentId) {
      const shouldNotifyParent = actionsResp.target === "app";
      // If the actions are for the app, we don't need to prepend the address
      const actionsWithAddress = shouldNotifyParent
        ? actionsResp
        : prependAddressToActions(actionsResp, this.address!);
      this.parentManager?.applyActions(actionsWithAddress, shouldNotifyParent);
      if (shouldNotify && !shouldNotifyParent) this.notifyListeners();
      return;
    }
    if (actionsResp.actions.length === 0) return;
    const componentsTreeCopy = produce(this.componentsTree!, (draft) => {
      applyActions(draft, actionsResp.actions);
    });
    this.componentsTree = componentsTreeCopy;
    if (shouldNotify) this.notifyListeners();
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
          lastURL: this.lastURL,
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
    if (this.address) {
      return this.parentManager?.getAtAddress(this.address) ?? [];
    }
    return this.componentsTree!;
  };

  isLoading = (): boolean => {
    return this.parentManager?.isLoading() || this._isLoading;
  };

  getError = (): Error | undefined => {
    return this.parentManager?.getError() ?? this._error;
  };

  getAtAddress = (address: number[]): RouteLitComponent[] => {
    const component = address.reduce(
      (acc, curr) =>
        Array.isArray(acc)
          ? acc[curr]
          : (acc as RouteLitComponent).children![curr],
      this.componentsTree as RouteLitComponent[] | RouteLitComponent
    );
    if (!component) throw new Error("Component not found");
    // @ts-ignore
    return Array.isArray(component) ? component : component.children;
  };

  subscribe = (listener: Handler): (() => void) => {
    const unsubscribeParent = this.parentManager?.subscribe(listener);
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
      unsubscribeParent?.();
    };
  };

  subscribeIsLoading = (listener: IsLoadingHandler): (() => void) => {
    const unsubscribeParent = this.parentManager?.subscribeIsLoading(listener);
    this.isLoadingListeners.push(listener);
    return () => {
      this.isLoadingListeners = this.isLoadingListeners.filter(
        (l) => l !== listener
      );
      unsubscribeParent?.();
    };
  };

  subscribeError = (listener: ErrorHandler): (() => void) => {
    const unsubscribeParent = this.parentManager?.subscribeError(listener);
    this.errorListeners.push(listener);
    return () => {
      this.errorListeners = this.errorListeners.filter((l) => l !== listener);
      unsubscribeParent?.();
    };
  };

  private notifyListeners = () => {
    const componentsTree = this.getComponentsTree();
    for (const listener of this.listeners) {
      listener(componentsTree);
    }
  };

  private notifyIsLoading = () => {
    const isLoading = this.isLoading();
    for (const listener of this.isLoadingListeners) {
      listener(isLoading);
    }
  };

  private notifyError = () => {
    const error = this.getError();
    for (const listener of this.errorListeners) {
      listener(error!);
    }
  };
}
