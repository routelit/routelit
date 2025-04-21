import { useCallback, useSyncExternalStore } from "react";
import { type RouteLitManager } from "./manager";
import { type ComponentStore } from "./component-store";

interface Props {
  manager: RouteLitManager;
  componentStore: ComponentStore;
}

function ReactRenderer({ manager, componentStore }: Props) {
  const componentsTree = useSyncExternalStore(
    manager.subscribe,
    manager.getComponentsTree
  );
  const componentStoreVersion = useSyncExternalStore(
    componentStore.subscribe,
    componentStore.getVersion
  );
  const renderComponentTree = useCallback(
    (c: RouteLitComponent): React.ReactNode => {
      const Component = componentStore.get(c.name);
      if (!Component) return null;
      return (
        <Component key={c.key} id={c.key} {...c.props}>
          {c.children?.map(renderComponentTree)}
        </Component>
      );
    },
    [componentStore]
  );
  return (
    <div className="routelit-container">
      <input type="hidden" name="componentStoreVersion" value={componentStoreVersion} />
      {componentsTree.map(renderComponentTree)}
    </div>
  );
}

export default ReactRenderer;
