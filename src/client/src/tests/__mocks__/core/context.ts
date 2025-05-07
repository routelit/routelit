import React from 'react';

export const RouteLitContext = React.createContext({
  manager: {
    initialize: jest.fn(),
    terminate: jest.fn(),
    handleEvent: jest.fn()
  },
  componentStore: {}
});

export const useDispatcherWith = jest.fn();
export const useDispatcherWithAttr = jest.fn();
export const useFormDispatcherWithAttr = jest.fn();
export const useFormDispatcher = jest.fn();
export const useIsLoading = jest.fn();
export const useError = jest.fn();
