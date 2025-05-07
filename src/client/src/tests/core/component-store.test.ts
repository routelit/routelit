import { ComponentStore } from '../../core/component-store';

describe('ComponentStore', () => {
  it('should register components', () => {
    const store = new ComponentStore();
    const TestComponent = () => null;

    store.register('test', TestComponent);

    expect(store.get('test')).toBe(TestComponent);
  });

  it('should unregister components', () => {
    const store = new ComponentStore();
    const TestComponent = () => null;

    store.register('test', TestComponent);
    store.unregister('test');

    expect(store.get('test')).toBeUndefined();
  });

  it('should notify listeners when version changes', () => {
    const store = new ComponentStore();
    const listener = jest.fn();

    store.subscribe(listener);
    store.register('test', () => null);

    expect(listener).toHaveBeenCalledWith(1);
  });

  it('should unsubscribe listeners', () => {
    const store = new ComponentStore();
    const listener = jest.fn();

    const unsubscribe = store.subscribe(listener);
    unsubscribe();
    store.register('test', () => null);

    expect(listener).not.toHaveBeenCalled();
  });

  it('should increment version when registering components', () => {
    const store = new ComponentStore();

    expect(store.getVersion()).toBe(0);

    store.register('test1', () => null);
    expect(store.getVersion()).toBe(1);

    store.register('test2', () => null);
    expect(store.getVersion()).toBe(2);
  });

  it('should increment version when forceUpdate is called', () => {
    const store = new ComponentStore();
    const listener = jest.fn();

    store.subscribe(listener);
    store.forceUpdate();

    expect(store.getVersion()).toBe(1);
    expect(listener).toHaveBeenCalledWith(1);
  });
});
