
export class ComponentStore {
  private listeners: Array<(v: number) => void> = [];
  private componentStore: Map<string, React.ComponentType<any>> = new Map();
  private version = 0;

  constructor() {}

  register = (name: string, component: React.ComponentType<any>) => {
    this.componentStore.set(name, component);
    this.version++;
    this.notifyListeners();
  }

  unregister = (name: string) => {
    this.componentStore.delete(name);
    this.version++;
  }

  get = (name: string) => {
    return this.componentStore.get(name);
  }

  getVersion = () => {
    return this.version;
  }

  subscribe = (listener: (v: number) => void) => {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  notifyListeners = () => {
    for (const listener of this.listeners) {
      listener(this.version);
    }
  }

  forceUpdate = () => {
    this.version++;
    this.notifyListeners();
  }
}

