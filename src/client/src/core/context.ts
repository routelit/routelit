import { createContext, useContext, useCallback } from "react";
import { type ComponentStore } from "./component-store";
import { type RouteLitManager } from "./manager";

type RouteLitContextType = {
  manager: RouteLitManager;
  componentStore: ComponentStore;
  parentManager?: RouteLitManager;
};

export const RouteLitContext = createContext<RouteLitContextType>({
  manager: undefined as unknown as RouteLitManager,
  componentStore: undefined as unknown as ComponentStore,
  parentManager: undefined as unknown as RouteLitManager,
});

export function useRouteLitContext() {
  const context = useContext(RouteLitContext);
  if (!context) {
    throw new Error(
      "useRouteLitContext must be used within a RouteLitContext.Provider"
    );
  }
  return context;
}

export function useDispatcher() {
  const { manager } = useRouteLitContext();
  return (event: CustomEvent<UIEventPayload>) => {
    manager.handleEvent(event);
  };
}

export function useDispatcherWith(id: string, type: string) {
  const { manager } = useRouteLitContext();
  const callback = useCallback(
    (data: Record<string, unknown>) => {
      manager.handleEvent(
        new CustomEvent<UIEventPayload>("routelit:event", {
          detail: { id, type, ...data },
        })
      );
    },
    [manager, id, type]
  );
  return callback;
}

export function useDispatcherWithAttr(id: string, type: string, attr: string) {
  const { manager } = useRouteLitContext();
  const callback = useCallback(
    (value: unknown) => {
      manager.handleEvent(
        new CustomEvent<UIEventPayload>("routelit:event", {
          detail: { id, type, [attr]: value },
        })
      );
    },
    [manager, id, type, attr]
  );
  return callback;
}
