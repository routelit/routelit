import { useCallback, useSyncExternalStore } from "react";
import { type RouteLitManager } from "./manager";

function ReactRenderer({ manager }: { manager: RouteLitManager }) {
  const componentsTree = useSyncExternalStore(
    manager.subscribe,
    manager.getComponentsTree
  );
  const componentStoreVersion = useSyncExternalStore(
    manager.subscribeComponentStoreVersion,
    manager.getComponentStoreVersion
  );
  const renderComponentTree = useCallback(
    (c: RouteLitComponent): React.ReactNode => {
      const Component = manager.getComponent(c.name);
      if (!Component) return null;
      return (
        <Component key={c.key} id={c.key} {...c.props}>
          {c.children?.map(renderComponentTree)}
        </Component>
      );
    },
    [manager]
  );
  return (
    <div className="routelit-container">
      <input type="hidden" name="componentStoreVersion" value={componentStoreVersion} />
      {componentsTree.map(renderComponentTree)}
    </div>
  );
}

export default ReactRenderer;
