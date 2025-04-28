import { useMemo } from "react";
import { useRouteLitContext, RouteLitContext } from "../core/context";
import ReactRenderer from "../core/react-renderer";
import { RouteLitManager } from "../core/manager";

interface Props {
  id?: string;
  address?: number[];
}

function Fragment({ id, address }: Props) {
  const { componentStore, manager: parentManager } = useRouteLitContext();
  const manager = useMemo(
    () => new RouteLitManager({ fragmentId: id, parentManager, address }),
    [address, id, parentManager]
  );
  return (
    <RouteLitContext.Provider value={{ manager, componentStore }}>
      <ReactRenderer manager={manager} componentStore={componentStore} />
    </RouteLitContext.Provider>
  );
}

export default Fragment;
