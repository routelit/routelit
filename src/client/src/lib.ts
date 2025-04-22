import React from 'react';
import * as ReactDOM from 'react-dom';
import * as jsxRuntime from 'react/jsx-runtime';

import initManager from './core/initializer';
import { ComponentStore } from './core/component-store';
import Fragment from './components/fragment';
import Link from './components/link';
import { useDispatcherWith, useDispatcherWithAttr } from './core/context';

const manager = initManager("routelit-data");
const componentStore = new ComponentStore();
export {
  useDispatcherWith,
  manager,
  componentStore,
  useDispatcherWithAttr,
};

componentStore.register("fragment", Fragment);
componentStore.register("link", Link);
componentStore.forceUpdate();

const RoutelitClient = {
  manager,
  componentStore,
  useDispatcherWith,
  useDispatcherWithAttr,
};

// Extend Window interface
declare global {
  interface Window {
    React: typeof React;
    ReactDOM: typeof ReactDOM;
    jsxRuntime: typeof jsxRuntime;
    RoutelitClient: typeof RoutelitClient;
  }
}

// Expose them globally
window.React = React;
window.ReactDOM = ReactDOM;
window.jsxRuntime = jsxRuntime;
window.RoutelitClient = RoutelitClient;

export { React, ReactDOM, jsxRuntime, RoutelitClient };
