import { useMemo } from "react";
import { useRouteLitContext, RouteLitContext } from "../core/context";
import ReactRenderer from "../core/react-renderer";
import { RouteLitManager } from "../core/manager";

interface Props {
  fragmentId?: string;
  children: RouteLitComponent[];
}

function Fragment({ fragmentId, children }: Props) {
  const { componentStore } = useRouteLitContext();
  const manager = useMemo(
    () => new RouteLitManager(children, fragmentId),
    [children, fragmentId]
  );
  return (
    <RouteLitContext.Provider value={{ manager, componentStore }}>
      <ReactRenderer manager={manager} componentStore={componentStore} />
    </RouteLitContext.Provider>
  );
}

export default Fragment;
