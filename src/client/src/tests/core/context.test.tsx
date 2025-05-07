import React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

// Mock the context module directly
jest.mock('../../core/context', () => {
  const mockDispatcherWithFn = jest.fn((id, type) => {
    return (data: any) => {
      mockHandleEvent({
        type: 'routelit:event',
        detail: { id, type, ...data }
      });
    };
  });

  const mockDispatcherWithAttrFn = jest.fn((id, type, attr) => {
    return (value: any) => {
      mockHandleEvent({
        type: 'routelit:event',
        detail: { id, type, [attr]: value }
      });
    };
  });

  const mockIsLoading = jest.fn(() => false);
  const mockGetError = jest.fn(() => undefined);

  // Mock context
  const contextValue = {
    manager: {
      handleEvent: mockHandleEvent,
      subscribeIsLoading: jest.fn(() => () => {}),
      isLoading: mockIsLoading,
      subscribeError: jest.fn(() => () => {}),
      getError: mockGetError
    },
    componentStore: {}
  };

  return {
    RouteLitContext: React.createContext(contextValue),
    useRouteLitContext: jest.fn().mockReturnValue(contextValue),
    useDispatcherWith: mockDispatcherWithFn,
    useDispatcherWithAttr: mockDispatcherWithAttrFn,
    useFormDispatcherWithAttr: jest.fn(),
    useFormDispatcher: jest.fn(),
    useIsLoading: mockIsLoading,
    useError: mockGetError
  };
});

// Mock handler for events
const mockHandleEvent = jest.fn();

// Test components that use the hooks
const TestDispatcherWith = ({ id, type }: { id: string, type: string }) => {
  const { useDispatcherWith } = require('../../core/context');
  const dispatch = useDispatcherWith(id, type);
  return <button data-testid="dispatch-button" onClick={() => dispatch({ testData: 'value' })}>Dispatch</button>;
};

const TestDispatcherWithAttr = ({ id, type, attr }: { id: string, type: string, attr: string }) => {
  const { useDispatcherWithAttr } = require('../../core/context');
  const dispatch = useDispatcherWithAttr(id, type, attr);
  return <button data-testid="dispatch-attr-button" onClick={() => dispatch('attr-value')}>Dispatch Attr</button>;
};

const TestIsLoading = () => {
  const { useIsLoading } = require('../../core/context');
  const isLoading = useIsLoading();
  return <div data-testid="loading-status">{isLoading ? 'Loading' : 'Not loading'}</div>;
};

const TestUseError = () => {
  const { useError } = require('../../core/context');
  const error = useError();
  return <div data-testid="error-message">{error ? error.message : 'No error'}</div>;
};

describe('Context Hooks', () => {
  // Clean up after each test to remove rendered components
  afterEach(() => {
    cleanup();
    jest.clearAllMocks();
  });

  it('useDispatcherWith creates a function that dispatches events with the right parameters', () => {
    render(<TestDispatcherWith id="test-id" type="test-type" />);

    fireEvent.click(screen.getByTestId('dispatch-button'));

    expect(mockHandleEvent).toHaveBeenCalledTimes(1);

    // Check the event object
    const event = mockHandleEvent.mock.calls[0][0];
    expect(event.type).toBe('routelit:event');
    expect(event.detail).toEqual({
      id: 'test-id',
      type: 'test-type',
      testData: 'value'
    });
  });

  it('useDispatcherWithAttr creates a function that dispatches events with attribute values', () => {
    render(<TestDispatcherWithAttr id="test-id" type="test-type" attr="testAttr" />);

    fireEvent.click(screen.getByTestId('dispatch-attr-button'));

    expect(mockHandleEvent).toHaveBeenCalledTimes(1);

    // Check the event object
    const event = mockHandleEvent.mock.calls[0][0];
    expect(event.type).toBe('routelit:event');
    expect(event.detail).toEqual({
      id: 'test-id',
      type: 'test-type',
      testAttr: 'attr-value'
    });
  });

  it('useIsLoading returns the loading state from the manager', () => {
    // Import the mock module to modify it
    const contextModule = require('../../core/context');

    // First test with isLoading = false
    contextModule.useIsLoading.mockReturnValue(false);

    const { unmount } = render(<TestIsLoading />);
    expect(screen.getByTestId('loading-status')).toHaveTextContent('Not loading');

    // Unmount the first component
    unmount();

    // Rerender with isLoading = true
    contextModule.useIsLoading.mockReturnValue(true);

    render(<TestIsLoading />);
    expect(screen.getByTestId('loading-status')).toHaveTextContent('Loading');
  });

  it('useError returns the error from the manager', () => {
    // Import the mock module to modify it
    const contextModule = require('../../core/context');

    // First test with no error
    contextModule.useError.mockReturnValue(undefined);

    const { unmount } = render(<TestUseError />);
    expect(screen.getByTestId('error-message')).toHaveTextContent('No error');

    // Unmount the first component
    unmount();

    // Rerender with an error
    const testError = new Error('Test error message');
    contextModule.useError.mockReturnValue(testError);

    render(<TestUseError />);
    expect(screen.getByTestId('error-message')).toHaveTextContent('Test error message');
  });
});
