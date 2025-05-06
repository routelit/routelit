import { useEffect } from "react";
import ReactRenderer from "./core/react-renderer";
import { manager, componentStore } from "./lib";
import { RouteLitContext } from "./core/context";

function App() {
  useEffect(() => {
    manager.initialize();
    return () => {
      manager.terminate();
    };
  }, []);

  return (
    <RouteLitContext.Provider value={{ manager, componentStore }}>
      <ReactRenderer manager={manager} componentStore={componentStore} />
    </RouteLitContext.Provider>
  );
}

export default App;
