import React from 'react';
import * as ReactDOM from 'react-dom';
import * as jsxRuntime from 'react/jsx-runtime';

import initManager from './core/initializer';
import { ComponentStore } from './core/component-store';
export const manager = initManager("routelit-data");
export const componentStore = new ComponentStore();

const RoutelitClient = {
  manager,
  componentStore,
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
