import React from 'react';
import { render, screen } from '@testing-library/react';
import Fragment from '../../components/fragment';
import ReactRenderer from '../../core/react-renderer';
import { RouteLitManager } from '../../core/manager';

// Mock the context module completely
jest.mock('../../core/context', () => {
  const contextValue = { manager: {}, componentStore: {} };

  return {
    RouteLitContext: {
      Provider: ({ children, value }: { children: React.ReactNode, value: any }) => {
        return <div data-testid="context-provider">{children}</div>;
      },
    },
    useRouteLitContext: jest.fn().mockReturnValue(contextValue)
  };
});

// Mock dependencies
jest.mock('../../core/react-renderer', () => {
  return {
    __esModule: true,
    default: jest.fn(() => <div data-testid="mock-renderer">Mocked Renderer</div>)
  };
});

jest.mock('../../core/manager', () => {
  return {
    RouteLitManager: jest.fn()
  };
});

describe('Fragment Component', () => {
  const mockComponentStore = {
    subscribe: jest.fn(),
    getVersion: jest.fn(),
    get: jest.fn(),
    register: jest.fn(),
    unregister: jest.fn(),
    forceUpdate: jest.fn()
  };

  const mockParentManager = {
    initialize: jest.fn(),
    terminate: jest.fn(),
    subscribe: jest.fn(),
    getComponentsTree: jest.fn()
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (RouteLitManager as jest.Mock).mockImplementation(() => ({
      fragmentId: 'test-fragment',
      initialize: jest.fn(),
      terminate: jest.fn()
    }));
  });

  it('renders a ReactRenderer with the correct props', () => {
    render(<Fragment id="test-fragment" />);

    expect(screen.getByTestId('mock-renderer')).toBeInTheDocument();
    expect(RouteLitManager).toHaveBeenCalledWith(
      expect.objectContaining({
        fragmentId: 'test-fragment',
        address: undefined
      })
    );
    expect(ReactRenderer).toHaveBeenCalled();
  });

  it('passes address to the RouteLitManager when provided', () => {
    const mockAddress = [1, 2, 3];
    render(<Fragment id="test-fragment" address={mockAddress} />);

    expect(RouteLitManager).toHaveBeenCalledWith(
      expect.objectContaining({
        fragmentId: 'test-fragment',
        address: mockAddress
      })
    );
  });

  it('only creates a new RouteLitManager when props change', () => {
    const { rerender } = render(<Fragment id="test-fragment" />);

    expect(RouteLitManager).toHaveBeenCalledTimes(1);

    // Rerender with the same props
    rerender(<Fragment id="test-fragment" />);

    // Should not create a new manager
    expect(RouteLitManager).toHaveBeenCalledTimes(1);

    // Rerender with different props
    rerender(<Fragment id="different-id" />);

    // Should create a new manager
    expect(RouteLitManager).toHaveBeenCalledTimes(2);
  });
});
