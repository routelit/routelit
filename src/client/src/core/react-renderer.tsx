import { useSyncExternalStore } from "react";
import { type RouteLitManager } from "./manager";
import { type ComponentStore } from "./component-store";
import Fragment from "../components/fragment";

interface Props {
  manager: RouteLitManager;
  componentStore: ComponentStore;
}

function ReactRenderer({ manager, componentStore }: Props) {
  const componentsTree = useSyncExternalStore(
    manager.subscribe,
    manager.getComponentsTree
  );
  // @ts-ignore
  const _componentStoreVersion = useSyncExternalStore(
    componentStore.subscribe,
    componentStore.getVersion
  );
  const renderComponentTree = (c: RouteLitComponent): React.ReactNode => {
    const Component = componentStore.get(c.name);
    if (!Component) return null;
    if (c.name === "fragment") {
      const { id, ...props } = c.props;
      return (
        <Fragment key={c.key} id={id as string} address={c.address} {...props} />
      );
    }

    return (
      <Component key={c.key} id={c.key} {...c.props}>
        {c.children?.map(renderComponentTree)}
      </Component>
    );
  };
  return (
    <div className="routelit-container">
      {componentsTree.map(renderComponentTree)}
    </div>
  );
}

export default ReactRenderer;
