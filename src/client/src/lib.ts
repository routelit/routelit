import React from "react";
import * as ReactDOM from "react-dom";
import * as jsxRuntime from "react/jsx-runtime";

import initManager from "./core/initializer";
import { ComponentStore } from "./core/component-store";
import Fragment from "./components/fragment";
import Link from "./components/link";
import Dialog from "./components/dialog";
import Form from "./components/form";
import Head from "./components/head";
import Container from "./components/container";
import Markdown from "./components/markdown";
import Image from "./components/image";
import {
  useDispatcherWith,
  useDispatcherWithAttr,
  useFormDispatcherWithAttr,
  useFormDispatcher,
  useIsLoading,
  useError,
} from "./core/context";
import { RouteLitManager } from "./core/manager";

// Define the type for our client interface
export interface RoutelitClientType {
  manager: RouteLitManager;
  componentStore: ComponentStore;
  useDispatcherWith: typeof useDispatcherWith;
  useDispatcherWithAttr: typeof useDispatcherWithAttr;
  useFormDispatcherWithAttr: typeof useFormDispatcherWithAttr;
  useFormDispatcher: typeof useFormDispatcher;
  useIsLoading: typeof useIsLoading;
  useError: typeof useError;
}

// Check if we already have an instance in the window object
// This ensures we only ever have a single instance of these objects
let manager: RouteLitManager;
let componentStore: ComponentStore;

// Add this to the window type
declare global {
  interface Window {
    React: typeof React;
    ReactDOM: typeof ReactDOM;
    jsxRuntime: typeof jsxRuntime;
    RoutelitClient?: RoutelitClientType;
    componentStore?: ComponentStore;
  }
}

// Only create new instances if they don't already exist in the window
if (window.RoutelitClient) {
  manager = window.RoutelitClient.manager;
  componentStore = window.RoutelitClient.componentStore;
} else {
  manager = initManager("routelit-data");
  componentStore = new ComponentStore();

  // Register components
  componentStore.register("fragment", Fragment);
  componentStore.register("link", Link);
  componentStore.register("dialog", Dialog);
  componentStore.register("form", Form);
  componentStore.register("head", Head);
  componentStore.register("container", Container);
  componentStore.register("markdown", Markdown);
  componentStore.register("image", Image);
  componentStore.forceUpdate();
}

export {
  useDispatcherWith,
  manager,
  componentStore,
  useDispatcherWithAttr,
  useIsLoading,
  useError,
  useFormDispatcherWithAttr,
  useFormDispatcher,
};

const RoutelitClient: RoutelitClientType = {
  manager,
  componentStore,
  useDispatcherWith,
  useDispatcherWithAttr,
  useIsLoading,
  useError,
  useFormDispatcherWithAttr,
  useFormDispatcher,
};

// Expose them globally
window.React = React;
window.ReactDOM = ReactDOM;
window.jsxRuntime = jsxRuntime;
window.RoutelitClient = RoutelitClient;

export { React, ReactDOM, jsxRuntime, RoutelitClient };
