import { useEffect } from 'react';
import ReactRenderer from './core/react-renderer';
import { manager } from './lib';

function App() {
  useEffect(() => {
    manager.initialize();
    return () => {
      manager.terminate();
    }
  }, []);
  return (
    <ReactRenderer manager={manager} />
  )
}

export default App
